"""Tests for tool execution."""
import pytest

from app.core.tools import ToolExecutor, get_tool_schemas


def test_tool_schemas_exist():
    """Test that tool schemas are defined."""
    tools = [
        "read_inbox",
        "get_purchase_order",
        "post_supplier_invoice",
        "execute_payment",
    ]
    
    schemas = get_tool_schemas(tools)
    assert len(schemas) == 4
    assert all("function" in s for s in schemas)


def test_idempotency_key_generation():
    """Test idempotency key generation is stable."""
    executor = ToolExecutor()
    
    # Payment key
    args1 = {"supplier_invoice": "5105600031", "fiscal_year": "2026"}
    key1 = executor._generate_idempotency_key("execute_payment", args1)
    assert key1 == "pay:5105600031:2026"
    
    # Same args should give same key
    key2 = executor._generate_idempotency_key("execute_payment", args1)
    assert key1 == key2
    
    # Invoice posting key
    args2 = {"purchase_order": "4500017", "supplier_invoice_ref": "INV-2026-001"}
    key3 = executor._generate_idempotency_key("post_supplier_invoice", args2)
    assert key3 == "post:4500017:INV-2026-001"


# TODO: Add tests with mocked gateway
# - test_execute_tool_allow
# - test_execute_tool_deny
# - test_execute_tool_timeout
