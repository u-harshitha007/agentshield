"""Agent state machine and executor."""
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import structlog

from app.core.config import settings
from app.core.events import EventEmitter
from app.core.llm import OllamaClient
from app.core.memory import TaskMemory
from app.core.replay import ReplayManager
from app.core.replan import Replanner
from app.core.tools import ToolExecutor, get_tool_schemas
from app.db.models import TaskStatus

logger = structlog.get_logger()


class AgentExecutor:
    """Agent executor with state machine."""
    
    def __init__(self):
        self.llm = OllamaClient()
        self.tools = ToolExecutor()
        self.replanner = Replanner()
        self.events = EventEmitter()
        self.replay = ReplayManager()
        
    async def execute_task(self, task_id: str, goal: str, lease_id: str, lease_token: str):
        """
        Execute a task with the agent.
        
        State machine:
        RECEIVED → PLANNING → EXECUTING ⇄ REPLANNING → AWAITING_APPROVAL → COMPLETED/FAILED
        """
        start_time = time.time()
        
        # Initialize task memory
        memory = TaskMemory(task_id)
        
        context = {
            "goal": goal,
            "task_id": task_id,
            "current_step": 0,
            "max_steps": settings.max_steps,
            "tool_calls_count": 0,
            "llm_calls_count": 0,
            "replans_count": 0,
            "observations": [],
            "memory": memory,
            "status": TaskStatus.PLANNING.value,
            "pending_approvals": [],  # Track approval requests
        }
        
        logger.info("agent.task.started", task_id=task_id, goal=goal)
        
        # Emit task created event
        await self.events.emit("agent.task.created", {
            "task_id": task_id,
            "goal": goal,
            "lease_token_preview": lease_token[:20] + "..." if lease_token else None,
        })
        
        try:
            # PLANNING → EXECUTING loop
            while context["current_step"] < context["max_steps"]:
                # Budget checks
                if context["llm_calls_count"] >= settings.max_llm_calls:
                    raise Exception("LLM call budget exhausted")
                
                if context["tool_calls_count"] >= settings.max_tool_calls:
                    raise Exception("Tool call budget exhausted")
                
                if (time.time() - start_time) > settings.max_wall_seconds:
                    raise Exception("Wall time budget exhausted")
                
                # Determine available tools for this step
                available_tools = self._get_available_tools(context)
                
                # Ask LLM for next action
                logger.info(
                    "agent.planning",
                    step=context["current_step"],
                    available_tools=[t["function"]["name"] for t in available_tools],
                )
                
                context["llm_calls_count"] += 1
                
                # Check if in replay mode
                if self.replay.is_replay_mode():
                    # Get recorded action
                    action = self.replay.get_next_action()
                    
                    if action is None:
                        # Replay exhausted
                        raise Exception("Replay trace exhausted")
                    
                    logger.info(
                        "agent.action_replayed",
                        tool=action.get("tool"),
                        mode="REPLAY",
                    )
                else:
                    # Convert memory to dict for LLM context
                    llm_context = {
                        **context,
                        "memory": context["memory"].get_all() if isinstance(context["memory"], TaskMemory) else context["memory"],
                    }
                    
                    action = await self.llm.plan_action(llm_context, available_tools)
                
                tool_name = action["tool"]
                tool_args = action["args"]
                reasoning = action.get("reasoning", "")
                
                logger.info(
                    "agent.action_planned",
                    tool=tool_name,
                    reasoning=reasoning[:100],
                    mode="REPLAY" if self.replay.is_replay_mode() else "LIVE",
                )
                
                # Emit LLM call event
                await self.events.emit("agent.llm.call", {
                    "task_id": task_id,
                    "step": context["current_step"],
                    "tool_proposed": tool_name,
                    "llm_call_id": action.get("llm_call_id"),
                    "replay_mode": self.replay.is_replay_mode(),
                })
                
                # Execute tool through gateway
                context["status"] = TaskStatus.EXECUTING.value
                context["tool_calls_count"] += 1
                
                step_id = f"step-{context['current_step']}"
                
                decision = await self.tools.execute_tool(
                    tool_name=tool_name,
                    args=tool_args,
                    task_id=task_id,
                    step_id=step_id,
                    lease_id=lease_id,
                    lease_token=lease_token,
                )
                
                # Emit tool call event
                await self.events.emit("agent.tool.called", {
                    "task_id": task_id,
                    "step": context["current_step"],
                    "tool": tool_name,
                    "decision": decision["decision"],
                    "reason_code": decision.get("reason_code"),
                    "decision_id": decision.get("decision_id"),
                })
                
                # Record observation
                observation = {
                    "step": context["current_step"],
                    "tool": tool_name,
                    "decision": decision["decision"],
                    "reason_code": decision.get("reason_code"),
                    "result": decision.get("result"),
                    "decision_id": decision.get("decision_id"),
                }
                context["observations"].append(observation)
                
                # Handle decision
                if decision["decision"] == "ALLOW":
                    logger.info(
                        "agent.tool.allowed",
                        tool=tool_name,
                        decision_id=decision.get("decision_id"),
                    )
                    
                    # Update memory with result
                    self._update_memory(context, tool_name, decision.get("result"))
                    
                    # Check if task is complete
                    if tool_name == "complete_task":
                        context["status"] = TaskStatus.COMPLETED.value
                        logger.info("agent.task.completed", task_id=task_id)
                        
                        # Emit completion event
                        await self.events.emit("agent.task.completed", {
                            "task_id": task_id,
                            "steps": context["current_step"],
                            "tool_calls": context["tool_calls_count"],
                            "llm_calls": context["llm_calls_count"],
                            "replans": context["replans_count"],
                        })
                        
                        return context
                    
                elif decision["decision"] in ["DENY", "HOLD"]:
                    logger.warning(
                        "agent.tool.denied_or_held",
                        tool=tool_name,
                        decision=decision["decision"],
                        reason_code=decision.get("reason_code"),
                    )
                    
                    # REPLAN
                    context["status"] = TaskStatus.REPLANNING.value
                    context["replans_count"] += 1
                    
                    if context["replans_count"] > settings.max_replans:
                        raise Exception("Replan budget exhausted")
                    
                    # Get safe alternative
                    new_plan = self.replanner.choose_safe_alternative(
                        decision=decision,
                        original_tool=tool_name,
                        context=context,
                    )
                    
                    logger.info(
                        "agent.replanned",
                        original_tool=tool_name,
                        new_action=new_plan["action"],
                        reason=new_plan["reason"],
                    )
                    
                    # Emit replanning event
                    await self.events.emit("agent.replanned", {
                        "task_id": task_id,
                        "original_tool": tool_name,
                        "decision": decision["decision"],
                        "reason_code": decision.get("reason_code"),
                        "new_action": new_plan["action"],
                        "decision_id": decision.get("decision_id"),
                    })
                    
                    # Execute safe alternative if specified
                    if new_plan["action"] in ["flag", "request_approval"]:
                        # Execute the safe tool
                        approval_result = await self._execute_safe_action(
                            new_plan,
                            task_id,
                            step_id,
                            lease_id,
                            lease_token,
                            context,
                        )
                        
                        # If we requested approval, wait for it
                        if new_plan["action"] == "request_approval" and approval_result:
                            approval_id = approval_result.get("result", {}).get("approval_id")
                            if approval_id:
                                context["pending_approvals"].append({
                                    "approval_id": approval_id,
                                    "original_tool": tool_name,
                                    "original_args": tool_args,
                                    "step_id": step_id,
                                })
                                
                                # Check for approval (non-blocking for now)
                                approval_granted = await self._check_approval(approval_id, context)
                                
                                if approval_granted:
                                    # Retry the original operation with approval
                                    logger.info("approval.granted", approval_id=approval_id, retrying=tool_name)
                                    # Note: In full implementation, would retry here
                                    # For now, just log and continue
                    
                    # If action is "abort", break
                    if new_plan["action"] == "abort":
                        raise Exception(f"Task aborted: {new_plan['reason']}")
                
                context["current_step"] += 1
            
            # Max steps reached
            context["status"] = TaskStatus.FAILED.value
            logger.warning("agent.task.max_steps", task_id=task_id)
            return context
            
        except Exception as e:
            context["status"] = TaskStatus.FAILED.value
            context["failure_reason"] = str(e)
            logger.error("agent.task.failed", task_id=task_id, error=str(e))
            
            # Emit failure event
            await self.events.emit("agent.task.failed", {
                "task_id": task_id,
                "reason": str(e),
                "steps_completed": context["current_step"],
            })
            
            return context
    
    def _get_available_tools(self, context: dict) -> list:
        """Get tools available for current step."""
        observations = context.get("observations", [])
        
        # Start with inbox reading
        if not observations:
            return get_tool_schemas(["read_inbox"])
        
        # After reading inbox, can read documents and get PO/supplier data
        last_tools = [obs["tool"] for obs in observations[-3:]]
        
        if "read_inbox" in last_tools:
            return get_tool_schemas([
                "get_document_text",
                "get_purchase_order",
                "get_supplier",
                "flag_suspicious_message",
            ])
        
        # After gathering data, can post invoice
        if "get_purchase_order" in last_tools:
            return get_tool_schemas([
                "get_goods_receipts",
                "get_supplier_bank",
                "post_supplier_invoice",
                "flag_suspicious_message",
                "request_human_approval",
            ])
        
        # After posting invoice, can pay
        if "post_supplier_invoice" in last_tools:
            return get_tool_schemas([
                "execute_payment",
                "request_human_approval",
                "complete_task",
            ])
        
        # Default: read/control tools
        return get_tool_schemas([
            "read_inbox",
            "flag_suspicious_message",
            "request_human_approval",
            "complete_task",
        ])
    
    def _update_memory(self, context: dict, tool_name: str, result: dict | None):
        """Update task memory with tool result."""
        if not result:
            return
        
        memory = context.get("memory")
        
        # Use TaskMemory if available, otherwise fall back to dict
        if isinstance(memory, TaskMemory):
            # Store with appropriate source marking
            if tool_name in ["read_inbox", "get_document_text"]:
                # External content - mark as untrusted
                memory.store_fact(tool_name, result, source="external")
            else:
                # ERP data - trusted
                memory.store_fact(tool_name, result, source="erp")
        else:
            # Fallback to dict (for backward compatibility)
            if not isinstance(memory, dict):
                memory = {}
            
            # Store key data
            if tool_name == "read_inbox" and "messages" in result:
                memory["inbox_messages"] = result["messages"]
            elif tool_name == "get_purchase_order":
                memory["purchase_order"] = result
            elif tool_name == "get_supplier":
                memory["supplier"] = result
            elif tool_name == "get_goods_receipts":
                memory["goods_receipts"] = result
            elif tool_name == "post_supplier_invoice":
                memory["posted_invoice"] = result
            
            context["memory"] = memory
    
    async def _execute_safe_action(
        self,
        plan: dict,
        task_id: str,
        step_id: str,
        lease_id: str,
        lease_token: str,
        context: dict,
    ) -> dict | None:
        """Execute a safe alternative action."""
        if plan["action"] == "flag":
            # Flag suspicious message
            memory = context.get("memory")
            
            # Get message_id from memory
            if isinstance(memory, TaskMemory):
                inbox_data = memory.get_fact("read_inbox")
                messages = inbox_data.get("messages", []) if inbox_data else []
            else:
                messages = memory.get("inbox_messages", []) if isinstance(memory, dict) else []
            
            message_id = messages[0].get("message_id", "unknown") if messages else "unknown"
            
            result = await self.tools.execute_tool(
                tool_name="flag_suspicious_message",
                args={
                    "message_id": message_id,
                    "reason": plan["reason"],
                },
                task_id=task_id,
                step_id=f"{step_id}-flag",
                lease_id=lease_id,
                lease_token=lease_token,
            )
            return result
        
        elif plan["action"] == "request_approval":
            # Request human approval
            result = await self.tools.execute_tool(
                tool_name="request_human_approval",
                args={
                    "action_summary": plan.get("action_summary", "Sensitive action needs approval"),
                    "reason": plan["reason"],
                },
                task_id=task_id,
                step_id=f"{step_id}-approval",
                lease_id=lease_id,
                lease_token=lease_token,
            )
            return result
        
        return None
    
    async def _check_approval(self, approval_id: str, context: dict) -> bool:
        """
        Check if approval has been granted (non-blocking).
        
        In full implementation, this would poll the gateway.
        For now, returns False to not block task execution.
        """
        try:
            # Would poll gateway: GET /v1/approvals/{approval_id}
            # For now, just log and continue
            logger.info("approval.check", approval_id=approval_id, status="pending")
            return False
        except Exception as e:
            logger.warning("approval.check_failed", approval_id=approval_id, error=str(e))
            return False
