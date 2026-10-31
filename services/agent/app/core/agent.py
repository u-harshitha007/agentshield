"""Agent state machine and executor."""
import asyncio
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
            "denied_tools": set(),
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
                reasoning = action.get("reasoning") or ""
                
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
                context["observations"].append({
                    "type": "llm_call",
                    "step": context["current_step"],
                    "tool_proposed": tool_name,
                    "llm_call_id": action.get("llm_call_id"),
                    "reasoning": reasoning[:200] if reasoning else "",
                })

                # Never retry a tool that the gateway already DENY'd.
                if tool_name in context["denied_tools"]:
                    logger.warning("agent.denied_tool_retry_blocked", tool=tool_name)
                    context["observations"].append({
                        "type": "replan",
                        "step": context["current_step"],
                        "tool": tool_name,
                        "tool_name": tool_name,
                        "decision": "DENY",
                        "reason_code": "DENY_RETRY_BLOCKED",
                        "message": "Blocked retry of a previously denied tool",
                    })
                    context["current_step"] += 1
                    continue
                
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
                    "type": "tool_call",
                    "step": context["current_step"],
                    "tool": tool_name,
                    "tool_name": tool_name,
                    "decision": decision["decision"],
                    "reason_code": decision.get("reason_code"),
                    "result": decision.get("result"),
                    "decision_id": decision.get("decision_id"),
                    "approval_id": decision.get("approval_id"),
                    "safe_alternatives": decision.get("safe_alternatives", []),
                    "message": decision.get("message"),
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

                elif decision["decision"] == "HOLD":
                    logger.warning(
                        "agent.tool.held",
                        tool=tool_name,
                        reason_code=decision.get("reason_code"),
                        approval_id=decision.get("approval_id"),
                    )
                    context["status"] = TaskStatus.AWAITING_APPROVAL.value
                    approval_id = decision.get("approval_id")
                    if not approval_id:
                        raise Exception("Gateway HOLD without approval_id; failing closed")

                    approval = await self._poll_approval(approval_id, timeout_seconds=25)
                    context["observations"].append({
                        "type": "approval",
                        "step": context["current_step"],
                        "approval_id": approval_id,
                        "status": approval.get("status"),
                        "decision": approval.get("decision"),
                    })

                    if approval.get("granted"):
                        logger.info("approval.granted", approval_id=approval_id, retrying=tool_name)
                        context["status"] = TaskStatus.EXECUTING.value
                        context["tool_calls_count"] += 1
                        retry_decision = await self.tools.execute_tool(
                            tool_name=tool_name,
                            args=tool_args,
                            task_id=task_id,
                            step_id=f"{step_id}-approved-retry",
                            lease_id=lease_id,
                            lease_token=lease_token,
                        )
                        context["observations"].append({
                            "type": "tool_call",
                            "step": context["current_step"],
                            "tool": tool_name,
                            "tool_name": tool_name,
                            "decision": retry_decision.get("decision"),
                            "reason_code": retry_decision.get("reason_code"),
                            "result": retry_decision.get("result"),
                            "decision_id": retry_decision.get("decision_id"),
                            "message": retry_decision.get("message"),
                        })
                        if retry_decision.get("decision") == "ALLOW":
                            self._update_memory(context, tool_name, retry_decision.get("result"))
                        else:
                            # Fail closed: do not loop HOLD/DENY retries after a post-approval call.
                            context["denied_tools"].add(tool_name)
                            context["status"] = TaskStatus.REPLANNING.value
                    else:
                        context["denied_tools"].add(tool_name)
                        context["status"] = TaskStatus.REPLANNING.value
                        context["replans_count"] += 1
                        if context["replans_count"] > settings.max_replans:
                            raise Exception("Replan budget exhausted after HOLD timeout/denial")
                    
                elif decision["decision"] == "DENY":
                    logger.warning(
                        "agent.tool.denied",
                        tool=tool_name,
                        reason_code=decision.get("reason_code"),
                    )
                    context["denied_tools"].add(tool_name)
                    
                    # REPLAN — never retry the denied tool
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

                    context["observations"].append({
                        "type": "replan",
                        "step": context["current_step"],
                        "tool": tool_name,
                        "tool_name": tool_name,
                        "decision": decision["decision"],
                        "reason_code": decision.get("reason_code"),
                        "new_action": new_plan["action"],
                        "reason": new_plan["reason"],
                    })
                    
                    # Emit replanning event
                    await self.events.emit("agent.replanned", {
                        "task_id": task_id,
                        "original_tool": tool_name,
                        "decision": decision["decision"],
                        "reason_code": decision.get("reason_code"),
                        "new_action": new_plan["action"],
                        "decision_id": decision.get("decision_id"),
                    })
                    
                    # Execute safe alternative if specified. Never retry the denied tool.
                    if new_plan["action"] in ["flag", "request_approval"]:
                        await self._execute_safe_action(
                            new_plan,
                            task_id,
                            step_id,
                            lease_id,
                            lease_token,
                            context,
                        )
                    
                    # If action is "abort", break
                    if new_plan["action"] == "abort":
                        raise Exception(f"Task aborted: {new_plan['reason']}")
                else:
                    # Unknown decision — fail closed
                    raise Exception(f"Unknown gateway decision: {decision.get('decision')}")
                
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
        denied = context.get("denied_tools", set())
        tool_obs = [obs.get("tool") for obs in observations if obs.get("tool")]
        
        # Keep the list small, but always allow a terminal action.
        if not tool_obs:
            names = ["read_inbox", "get_supplier", "get_purchase_order", "complete_task"]
        else:
            last_tools = tool_obs[-3:]
            if "read_inbox" in last_tools:
                names = [
                    "get_document_text",
                    "get_purchase_order",
                    "get_supplier",
                    "post_supplier_invoice",
                    "execute_payment",
                    "flag_suspicious_message",
                    "complete_task",
                ]
            elif "get_purchase_order" in last_tools or "get_supplier" in last_tools:
                names = [
                    "get_goods_receipts",
                    "get_supplier_bank",
                    "post_supplier_invoice",
                    "execute_payment",
                    "flag_suspicious_message",
                    "request_human_approval",
                    "complete_task",
                ]
            elif "post_supplier_invoice" in last_tools:
                names = [
                    "execute_payment",
                    "request_human_approval",
                    "complete_task",
                ]
            else:
                names = [
                    "read_inbox",
                    "get_supplier",
                    "post_supplier_invoice",
                    "execute_payment",
                    "flag_suspicious_message",
                    "request_human_approval",
                    "complete_task",
                ]

        names = [name for name in names if name not in denied]
        if "complete_task" not in denied:
            names = [name for name in names if name != "complete_task"][:5]
            names.append("complete_task")
        else:
            names = names[:6]
        return get_tool_schemas(names)
    
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
            context["observations"].append({
                "type": "tool_call",
                "step": context["current_step"],
                "tool": "flag_suspicious_message",
                "tool_name": "flag_suspicious_message",
                "decision": result.get("decision"),
                "reason_code": result.get("reason_code"),
                "decision_id": result.get("decision_id"),
                "result": result.get("result"),
            })
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
            context["observations"].append({
                "type": "tool_call",
                "step": context["current_step"],
                "tool": "request_human_approval",
                "tool_name": "request_human_approval",
                "decision": result.get("decision"),
                "reason_code": result.get("reason_code"),
                "decision_id": result.get("decision_id"),
                "result": result.get("result"),
            })
            return result
        
        return None
    
    async def _poll_approval(self, approval_id: str, timeout_seconds: int = 25) -> dict:
        """Poll gateway approval status. Timeout and errors fail closed (not granted)."""
        deadline = time.time() + timeout_seconds
        headers = {"Authorization": f"Bearer {settings.agent_service_token}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                while time.time() < deadline:
                    response = await client.get(
                        f"{settings.gateway_url}/v1/approvals/{approval_id}",
                        headers=headers,
                    )
                    if response.status_code != 200:
                        logger.warning(
                            "approval.poll_http_error",
                            approval_id=approval_id,
                            status_code=response.status_code,
                        )
                        await asyncio.sleep(2)
                        continue

                    data = response.json()
                    status = data.get("status")
                    decision = data.get("decision")
                    logger.info(
                        "approval.check",
                        approval_id=approval_id,
                        status=status,
                        decision=decision,
                    )
                    if status == "approved" and decision == "ALLOW":
                        return {"granted": True, "status": status, "decision": decision}
                    if status in {"denied", "rejected"} or decision == "DENY":
                        return {"granted": False, "status": status, "decision": decision}
                    await asyncio.sleep(2)
        except Exception as e:
            logger.warning("approval.check_failed", approval_id=approval_id, error=str(e))
            return {"granted": False, "status": "error", "decision": None}

        logger.warning("approval.timeout", approval_id=approval_id)
        return {"granted": False, "status": "timeout", "decision": None}
