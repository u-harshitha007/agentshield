"""Tests for replanning logic - the key security feature."""
import pytest

from app.core.replan import Replanner


def test_bank_name_mismatch_replan():
    """Test that bank name mismatch triggers flag + approval."""
    replanner = Replanner()
    
    decision = {
        "decision": "DENY",
        "reason_code": "DENY_BANK_NAME_MISMATCH",
        "inr_at_risk": 2500000,
        "safe_alternatives": ["flag_suspicious_message", "request_human_approval"],
    }
    
    plan = replanner.choose_safe_alternative(
        decision=decision,
        original_tool="update_supplier_bank",
        context={},
    )
    
    assert plan["action"] == "flag"
    # Accept Indian lakh format (₹25.00 lakh) or raw number
    assert ("25.00 lakh" in plan["reason"] or "25,00,000" in plan["reason"] or "2500000" in plan["reason"])
    assert "mismatch" in plan["reason"].lower()


def test_price_variance_replan():
    """Test that price variance triggers flag."""
    replanner = Replanner()
    
    decision = {
        "decision": "DENY",
        "reason_code": "DENY_PRICE_VARIANCE",
        "inr_at_risk": 270000,
        "safe_alternatives": ["flag_suspicious_message"],
    }
    
    plan = replanner.choose_safe_alternative(
        decision=decision,
        original_tool="post_supplier_invoice",
        context={},
    )
    
    assert plan["action"] == "flag"
    assert "price" in plan["reason"].lower()


def test_hold_needs_approval_replan():
    """Test that HOLD triggers approval request."""
    replanner = Replanner()
    
    decision = {
        "decision": "HOLD",
        "reason_code": "HOLD_AMOUNT_NEEDS_APPROVAL",
        "inr_at_risk": 300000,
        "safe_alternatives": ["request_human_approval"],
    }
    
    plan = replanner.choose_safe_alternative(
        decision=decision,
        original_tool="execute_payment",
        context={},
    )
    
    assert plan["action"] == "request_approval"
    assert "approval" in plan["reason"].lower()


def test_lease_denied_abort():
    """Test that lease issues trigger abort."""
    replanner = Replanner()
    
    decision = {
        "decision": "DENY",
        "reason_code": "DENY_LEASE_EXPIRED",
        "safe_alternatives": ["abort_task"],
    }
    
    plan = replanner.choose_safe_alternative(
        decision=decision,
        original_tool="execute_payment",
        context={},
    )
    
    assert plan["action"] == "abort"


def test_duplicate_payment_skip():
    """Test that duplicate payment triggers skip."""
    replanner = Replanner()
    
    decision = {
        "decision": "DENY",
        "reason_code": "DENY_DUPLICATE_PAYMENT",
        "safe_alternatives": ["skip_step"],
    }
    
    plan = replanner.choose_safe_alternative(
        decision=decision,
        original_tool="execute_payment",
        context={},
    )
    
    assert plan["action"] == "skip"
