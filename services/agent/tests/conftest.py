"""Pytest configuration and fixtures."""
import pytest


@pytest.fixture
def mock_gateway_response_allow():
    """Mock gateway response for ALLOW decision."""
    return {
        "decision_id": "test-decision-123",
        "decision": "ALLOW",
        "reason_code": "ALLOW_OK",
        "message": "Operation allowed",
        "inr_at_risk": 0,
        "formula": None,
        "checks": [{"name": "lease.signature", "result": "pass"}],
        "result": {"test": "data"},
        "approval_id": None,
        "safe_alternatives": [],
        "correlation_id": "test-task-123",
        "idempotent_replay": False,
    }


@pytest.fixture
def mock_gateway_response_deny():
    """Mock gateway response for DENY decision."""
    return {
        "decision_id": "test-decision-456",
        "decision": "DENY",
        "reason_code": "DENY_BANK_NAME_MISMATCH",
        "message": "Bank account holder name does not match supplier",
        "inr_at_risk": 2500000,
        "formula": None,
        "checks": [
            {"name": "lease.signature", "result": "pass"},
            {"name": "oracle.bank_name", "result": "fail", "detail": "score 45 < 70"},
        ],
        "result": None,
        "approval_id": None,
        "safe_alternatives": [
            "flag_suspicious_message",
            "request_human_approval",
            "abort_task",
        ],
        "correlation_id": "test-task-123",
        "idempotent_replay": False,
    }


@pytest.fixture
def mock_gateway_response_hold():
    """Mock gateway response for HOLD decision."""
    return {
        "decision_id": "test-decision-789",
        "decision": "HOLD",
        "reason_code": "HOLD_AMOUNT_NEEDS_APPROVAL",
        "message": "Amount exceeds approval threshold",
        "inr_at_risk": 300000,
        "formula": "₹3,00,000 > approval threshold ₹2,00,000",
        "checks": [{"name": "lease.signature", "result": "pass"}],
        "result": None,
        "approval_id": "approval-123",
        "safe_alternatives": ["request_human_approval", "skip_step"],
        "correlation_id": "test-task-123",
        "idempotent_replay": False,
    }
