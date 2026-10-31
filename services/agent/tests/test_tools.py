"""Tests for tool execution."""
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_execute_tool_sends_contract_payload_and_lease_header():
    """Agent must send the gateway contract body plus X-Lease, never ERP URLs."""
    executor = ToolExecutor()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "decision": "ALLOW",
        "reason_code": "ALLOW_OK",
        "decision_id": "d1",
        "result": {"ok": True},
    }
    mock_post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post
        result = await executor.execute_tool(
            tool_name="get_supplier",
            args={"supplier": "SUP-12345"},
            task_id="task-1",
            step_id="step-0",
            lease_id="lease-1",
            lease_token="token-abc",
        )

    assert result["decision"] == "ALLOW"
    url = mock_post.call_args.args[0]
    assert url.endswith("/v1/tool-calls")
    assert "erp" not in url.lower()
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["X-Lease"] == "token-abc"
    assert headers["Authorization"].startswith("Bearer ")
    assert "Idempotency-Key" not in headers
    body = mock_post.call_args.kwargs["json"]
    assert body["task_id"] == "task-1"
    assert body["lease_id"] == "lease-1"
    assert body["tool_name"] == "get_supplier"
    assert body["tool_args"] == {"supplier": "SUP-12345"}
    assert body["context"]["step_id"] == "step-0"
    assert body["call_id"]


@pytest.mark.asyncio
async def test_execute_write_tool_sends_idempotency_key():
    """Write tools must send a stable Idempotency-Key header."""
    executor = ToolExecutor()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"decision": "ALLOW", "reason_code": "ALLOW_OK"}
    mock_post = AsyncMock(return_value=mock_response)

    args = {"supplier_invoice": "5105600031", "fiscal_year": "2026", "amount_inr": 1000}
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post
        await executor.execute_tool(
            tool_name="execute_payment",
            args=args,
            task_id="task-1",
            step_id="step-1",
            lease_id="lease-1",
            lease_token="token-abc",
        )

    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Idempotency-Key"] == "pay:5105600031:2026"


@pytest.mark.asyncio
async def test_execute_tool_fail_closed_on_401():
    """Auth failures must DENY, never look like an ALLOW."""
    executor = ToolExecutor()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"detail": "unauthorized"}
    mock_post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post
        result = await executor.execute_tool(
            tool_name="get_supplier",
            args={"supplier": "SUP-1"},
            task_id="task-1",
            step_id="step-0",
            lease_id="lease-1",
            lease_token="token-abc",
        )

    assert result["decision"] == "DENY"
    assert result["reason_code"] == "DENY_LEASE_INVALID"


@pytest.mark.asyncio
async def test_execute_tool_fail_closed_without_lease():
    """Refuse to call the gateway when lease material is missing."""
    executor = ToolExecutor()
    with patch("httpx.AsyncClient") as mock_client:
        result = await executor.execute_tool(
            tool_name="get_supplier",
            args={"supplier": "SUP-1"},
            task_id="task-1",
            step_id="step-0",
            lease_id="",
            lease_token="",
        )
    mock_client.assert_not_called()
    assert result["decision"] == "DENY"
    assert result["reason_code"] == "DENY_LEASE_INVALID"
