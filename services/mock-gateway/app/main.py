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
- MOCK_SERVICE_TOKEN: Bearer token required on mutating/protected endpoints
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Load local .env without adding a dotenv dependency.
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for raw in _env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

# Configuration
DEFAULT_DECISION = os.getenv("MOCK_DECISION", "ALLOW")  # ALLOW, DENY, HOLD
HIGH_RISK_TOOLS = [
    item.strip()
    for item in os.getenv("HIGH_RISK_TOOLS", "execute_payment,delete_supplier").split(",")
    if item.strip()
]
APPROVAL_THRESHOLD_INR = int(os.getenv("APPROVAL_THRESHOLD_INR", "200000"))
SERVICE_TOKEN = os.getenv("MOCK_SERVICE_TOKEN", "local-agent-token")

app = FastAPI(title="Mock Gateway", version="1.0.0")

# In-memory stores
approvals: dict[str, dict] = {}
leases: dict[str, dict] = {}


# === Request/Response Models ===

class LeaseRequest(BaseModel):
    task_id: str
    requested_by: str | None = "agent-service"
    policy_id: str | None = None
    template: str | None = None
    context: dict[str, Any] | None = None


class LeaseResponse(BaseModel):
    lease_id: str
    task_id: str
    signature: str
    expires_at: str
    lease_token: str


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

def _require_service_auth(authorization: str | None) -> None:
    """Fail closed if the agent service token is missing or wrong."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[len("Bearer "):].strip()
    if not token or token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid service token")


def _deny_lease(task_id: str, reason_code: str, message: str, checks: list[Check]) -> GatewayDecision:
    return GatewayDecision(
        decision_id=f"dec-{uuid.uuid4().hex[:12]}",
        decision="DENY",
        reason_code=reason_code,
        message=message,
        inr_at_risk=0,
        formula=None,
        checks=checks,
        result=None,
        approval_id=None,
        safe_alternatives=["abort_task"],
        correlation_id=task_id,
        idempotent_replay=False,
    )


def _verify_lease(request: ToolCallRequest, x_lease: str | None) -> GatewayDecision | None:
    """Return a DENY decision if the lease is missing, mismatched, or expired."""
    if not x_lease:
        return _deny_lease(
            request.task_id,
            "DENY_LEASE_INVALID",
            "X-Lease header is required",
            [Check(name="lease.token", result="fail", detail="missing X-Lease")],
        )

    record = leases.get(request.lease_id)
    if not record:
        return _deny_lease(
            request.task_id,
            "DENY_LEASE_INVALID",
            "Unknown lease_id",
            [Check(name="lease.id", result="fail", detail="lease not issued")],
        )

    if record["lease_token"] != x_lease:
        return _deny_lease(
            request.task_id,
            "DENY_LEASE_INVALID",
            "Lease token does not match issued lease",
            [Check(name="lease.token", result="fail", detail="token mismatch")],
        )

    if record["task_id"] != request.task_id:
        return _deny_lease(
            request.task_id,
            "DENY_LEASE_INVALID",
            "Lease was not issued for this task_id",
            [Check(name="lease.task", result="fail", detail="task mismatch")],
        )

    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        return _deny_lease(
            request.task_id,
            "DENY_LEASE_EXPIRED",
            "Lease has expired",
            [Check(name="lease.expiry", result="fail", detail="expired")],
        )

    return None


def _extract_amount(tool_args: dict) -> int | None:
    """Extract INR amount from tool arguments."""
    for key in [
        "amount",
        "amount_inr",
        "gross_amount_inr",
        "quoted_cost_inr",
        "value",
        "payment_amount",
    ]:
        if key in tool_args:
            val = tool_args[key]
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str):
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

    # Check for high-risk tools (DENY) — never overridden by a later approval.
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

    # A prior HOLD that was approved should ALLOW the same task+tool retry.
    if any(
        record.get("task_id") == task_id
        and record.get("tool_name") == tool_name
        and record.get("status") == "approved"
        and record.get("decision") == "ALLOW"
        for record in approvals.values()
    ):
        return GatewayDecision(
            decision_id=decision_id,
            decision="ALLOW",
            reason_code="ALLOW_OK",
            message="Operation allowed after human approval",
            inr_at_risk=0,
            formula=None,
            checks=[Check(name="lease.signature", result="pass"), Check(name="approval", result="pass")],
            result={"status": "success", "mock": True, "tool_name": tool_name, "approved": True},
            approval_id=None,
            safe_alternatives=[],
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
        result={"status": "success", "mock": True, "tool_name": tool_name, "tool_args": tool_args},
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
async def issue_lease(
    request: LeaseRequest,
    authorization: str | None = Header(default=None),
):
    """Issue a capability lease for a task."""
    _require_service_auth(authorization)

    lease_id = f"lease-{uuid.uuid4().hex[:12]}"
    signature = f"sig-{uuid.uuid4().hex[:16]}"
    lease_token = f"token-{uuid.uuid4().hex[:16]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    leases[lease_id] = {
        "lease_id": lease_id,
        "lease_token": lease_token,
        "task_id": request.task_id,
        "expires_at": expires_at,
    }

    return LeaseResponse(
        lease_id=lease_id,
        task_id=request.task_id,
        signature=signature,
        expires_at=expires_at,
        lease_token=lease_token,
    )


@app.post("/v1/tool-calls", response_model=GatewayDecision)
async def evaluate_tool_call(
    request: ToolCallRequest,
    authorization: str | None = Header(default=None),
    x_lease: str | None = Header(default=None),
):
    """Evaluate a tool call and return ALLOW/DENY/HOLD decision."""
    _require_service_auth(authorization)
    lease_denial = _verify_lease(request, x_lease)
    if lease_denial:
        return lease_denial
    return _make_decision(request.tool_name, request.tool_args, request.task_id)


@app.get("/v1/approvals/{approval_id}", response_model=ApprovalStatus)
async def get_approval_status(
    approval_id: str,
    authorization: str | None = Header(default=None),
):
    """Get approval status (for HOLD polling)."""
    _require_service_auth(authorization)

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
async def receive_event(
    event: EventPayload,
    authorization: str | None = Header(default=None),
):
    """Receive events from agent (no-op for mock)."""
    _require_service_auth(authorization)
    return {"status": "received", "event_type": event.event_type}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
