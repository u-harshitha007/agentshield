"""Mock Gateway Service for AgentShield local testing.

This is a minimal Gateway implementation for testing the Agent Runtime
without requiring Chandan's full Gateway module.

Endpoints:
- POST /v1/tasks - Issue capability lease
- POST /v1/tool-calls - Evaluate tool call
- GET /v1/approvals/{approval_id} - Check approval status
- POST /v1/events - Receive events (no-op)
- GET /health - Health check

Configuration:
- DEFAULT_DECISION: ALLOW, DENY, or HOLD (env: MOCK_DECISION)
- HIGH_RISK_TOOLS: Tools that trigger DENY (env: HIGH_RISK_TOOLS)
- APPROVAL_THRESHOLD_INR: Amount requiring approval (env: APPROVAL_THRESHOLD_INR)
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configuration
DEFAULT_DECISION = os.getenv("MOCK_DECISION", "ALLOW")  # ALLOW, DENY, HOLD
HIGH_RISK_TOOLS = os.getenv("HIGH_RISK_TOOLS", "execute_payment,delete_supplier").split(",")
APPROVAL_THRESHOLD_INR = int(os.getenv("APPROVAL_THRESHOLD_INR", "200000"))

app = FastAPI(title="Mock Gateway", version="1.0.0")

# In-memory approval store
approvals: dict[str, dict] = {}


# === Request/Response Models ===

class LeaseRequest(BaseModel):
    task_id: str
    requested_by: str | None = "agent-service"  # Default value
    policy_id: str | None = None


class LeaseResponse(BaseModel):
    lease_id: str
    task_id: str
    signature: str
    expires_at: str
    lease_token: str | None = None  # Added for agent compatibility


class ToolCallRequest(BaseModel):
    call_id: str
    task_id: str
    lease_id: str
    tool_name: str
    tool_args: dict[str, Any]
    context: dict[str, Any]


class Check(BaseModel):
    name: str
    result: str
    detail: str | None = None


class GatewayDecision(BaseModel):
    decision_id: str
    decision: str  # ALLOW, DENY, HOLD
    reason_code: str
    message: str
    inr_at_risk: int
    formula: str | None
    checks: list[Check]
    result: Any | None
    approval_id: str | None
    safe_alternatives: list[str]
    correlation_id: str
    idempotent_replay: bool


class ApprovalStatus(BaseModel):
    approval_id: str
    status: str  # pending, approved, denied
    decision: str | None  # ALLOW, DENY
    reason: str | None
    approved_by: str | None
    approved_at: str | None


class EventPayload(BaseModel):
    event_type: str
    payload: dict[str, Any]


# === Helper Functions ===

def _extract_amount(tool_args: dict) -> int | None:
    """Extract INR amount from tool arguments."""
    for key in ["amount", "amount_inr", "value", "payment_amount"]:
        if key in tool_args:
            val = tool_args[key]
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str):
                # Remove currency symbols and commas
                clean = val.replace("₹", "").replace(",", "").strip()
                try:
                    return int(float(clean))
                except ValueError:
                    pass
    return None


def _make_decision(tool_name: str, tool_args: dict, task_id: str) -> GatewayDecision:
    """Make a mock gateway decision based on configuration."""
    decision_id = f"dec-{uuid.uuid4().hex[:12]}"
    amount = _extract_amount(tool_args)
    
    # Check for high-risk tools (DENY)
    if tool_name in HIGH_RISK_TOOLS:
        return GatewayDecision(
            decision_id=decision_id,
            decision="DENY",
            reason_code="DENY_HIGH_RISK_TOOL",
            message=f"Tool '{tool_name}' is flagged as high-risk in mock config",
            inr_at_risk=amount or 0,
            formula=None,
            checks=[
                Check(name="lease.signature", result="pass"),
                Check(name="tool.risk_level", result="fail", detail="high-risk tool"),
            ],
            result=None,
            approval_id=None,
            safe_alternatives=["request_human_approval", "abort_task"],
            correlation_id=task_id,
            idempotent_replay=False,
        )
    
    # Check for amount threshold (HOLD)
    if amount and amount > APPROVAL_THRESHOLD_INR:
        approval_id = f"appr-{uuid.uuid4().hex[:12]}"
        approvals[approval_id] = {
            "approval_id": approval_id,
            "status": "pending",
            "tool_name": tool_name,
            "amount": amount,
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return GatewayDecision(
            decision_id=decision_id,
            decision="HOLD",
            reason_code="HOLD_AMOUNT_NEEDS_APPROVAL",
            message=f"Amount ₹{amount:,} exceeds approval threshold ₹{APPROVAL_THRESHOLD_INR:,}",
            inr_at_risk=amount,
            formula=f"₹{amount:,} > threshold ₹{APPROVAL_THRESHOLD_INR:,}",
            checks=[Check(name="lease.signature", result="pass")],
            result=None,
            approval_id=approval_id,
            safe_alternatives=["request_human_approval", "skip_step"],
            correlation_id=task_id,
            idempotent_replay=False,
        )
    
    # Default decision (configurable)
    if DEFAULT_DECISION == "DENY":
        return GatewayDecision(
            decision_id=decision_id,
            decision="DENY",
            reason_code="DENY_MOCK_CONFIG",
            message="Mock Gateway configured to DENY by default",
            inr_at_risk=amount or 0,
            formula=None,
            checks=[Check(name="lease.signature", result="pass")],
            result=None,
            approval_id=None,
            safe_alternatives=["abort_task"],
            correlation_id=task_id,
            idempotent_replay=False,
        )
    
    if DEFAULT_DECISION == "HOLD":
        approval_id = f"appr-{uuid.uuid4().hex[:12]}"
        approvals[approval_id] = {
            "approval_id": approval_id,
            "status": "pending",
            "tool_name": tool_name,
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return GatewayDecision(
            decision_id=decision_id,
            decision="HOLD",
            reason_code="HOLD_MOCK_CONFIG",
            message="Mock Gateway configured to HOLD by default",
            inr_at_risk=amount or 0,
            formula=None,
            checks=[Check(name="lease.signature", result="pass")],
            result=None,
            approval_id=approval_id,
            safe_alternatives=["request_human_approval"],
            correlation_id=task_id,
            idempotent_replay=False,
        )
    
    # ALLOW (default)
    return GatewayDecision(
        decision_id=decision_id,
        decision="ALLOW",
        reason_code="ALLOW_OK",
        message="Operation allowed by mock gateway",
        inr_at_risk=0,
        formula=None,
        checks=[Check(name="lease.signature", result="pass")],
        result={"status": "success", "mock": True},
        approval_id=None,
        safe_alternatives=[],
        correlation_id=task_id,
        idempotent_replay=False,
    )


# === Endpoints ===

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "mock-gateway"}


@app.post("/v1/tasks", response_model=LeaseResponse)
async def issue_lease(request: LeaseRequest):
    """Issue a capability lease for a task."""
    lease_id = f"lease-{uuid.uuid4().hex[:12]}"
    signature = f"sig-{uuid.uuid4().hex[:16]}"
    lease_token = f"token-{uuid.uuid4().hex[:16]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    
    return LeaseResponse(
        lease_id=lease_id,
        task_id=request.task_id,
        signature=signature,
        expires_at=expires_at,
        lease_token=lease_token,
    )


@app.post("/v1/tool-calls", response_model=GatewayDecision)
async def evaluate_tool_call(request: ToolCallRequest):
    """Evaluate a tool call and return ALLOW/DENY/HOLD decision."""
    return _make_decision(request.tool_name, request.tool_args, request.task_id)


@app.get("/v1/approvals/{approval_id}", response_model=ApprovalStatus)
async def get_approval_status(approval_id: str):
    """Get approval status (for HOLD polling)."""
    if approval_id not in approvals:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    approval = approvals[approval_id]
    
    # Mock: auto-approve after 10 seconds (for testing)
    created_at = datetime.fromisoformat(approval["created_at"])
    age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
    
    if age_seconds > 10 and approval["status"] == "pending":
        approval["status"] = "approved"
        approval["decision"] = "ALLOW"
        approval["approved_by"] = "mock-auto-approver"
        approval["approved_at"] = datetime.now(timezone.utc).isoformat()
    
    return ApprovalStatus(
        approval_id=approval["approval_id"],
        status=approval["status"],
        decision=approval.get("decision"),
        reason=approval.get("reason"),
        approved_by=approval.get("approved_by"),
        approved_at=approval.get("approved_at"),
    )


@app.post("/v1/events")
async def receive_event(event: EventPayload):
    """Receive events from agent (no-op for mock)."""
    return {"status": "received", "event_type": event.event_type}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
