"""Tool definitions and execution layer for calling gateway."""
import json
from typing import Any
from uuid import uuid4

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class ToolExecutor:
    """Executes tools by calling the gateway with lease verification."""
    
    def __init__(self):
        self.gateway_url = settings.gateway_url
        self.service_token = settings.agent_service_token
        
    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        task_id: str,
        step_id: str,
        lease_id: str,
        lease_token: str,
    ) -> dict[str, Any]:
        """
        Execute a tool through the gateway.
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            task_id: Current task ID
            step_id: Current step ID
            lease_id: Capability lease ID
            lease_token: Capability lease token
            
        Returns:
            Gateway decision response
        """
        if not lease_id or not lease_token:
            logger.error("tool.missing_lease", tool=tool_name, task_id=task_id)
            return {
                "decision": "DENY",
                "reason_code": "DENY_LEASE_INVALID",
                "message": "Missing lease_id or lease_token; refusing to call gateway",
                "checks": [],
            }

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"raw": args}
        if not isinstance(args, dict):
            args = {}

        call_id = str(uuid4())
        
        payload = {
            "call_id": call_id,
            "task_id": task_id,
            "lease_id": lease_id,
            "tool_name": tool_name,
            "tool_args": args,
            "context": {"step_id": step_id},
        }
        
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "X-Lease": lease_token,
            "Content-Type": "application/json",
        }
        if tool_name in self._write_tools():
            headers["Idempotency-Key"] = self._generate_idempotency_key(tool_name, args)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/tool-calls",
                    json=payload,
                    headers=headers,
                )

                try:
                    result = response.json()
                except Exception:
                    result = {"detail": response.text}

                logger.info(
                    "tool.executed",
                    tool=tool_name,
                    decision=result.get("decision") if isinstance(result, dict) else None,
                    reason_code=result.get("reason_code") if isinstance(result, dict) else None,
                    decision_id=result.get("decision_id") if isinstance(result, dict) else None,
                    status_code=response.status_code,
                )

                if response.status_code in (401, 403):
                    return {
                        "decision": "DENY",
                        "reason_code": "DENY_LEASE_INVALID",
                        "message": "Gateway rejected authentication or lease",
                        "checks": [],
                    }

                if response.status_code >= 400 or not isinstance(result, dict) or "decision" not in result:
                    return {
                        "decision": "DENY",
                        "reason_code": "DENY_DEPENDENCY_UNAVAILABLE",
                        "message": f"Gateway returned HTTP {response.status_code}",
                        "checks": [],
                    }

                return result
                
        except httpx.TimeoutException as e:
            logger.error("tool.timeout", tool=tool_name, error=str(e))
            return {
                "decision": "DENY",
                "reason_code": "DENY_DEPENDENCY_UNAVAILABLE",
                "message": "Gateway timeout",
                "checks": [],
            }
        except Exception as e:
            logger.error("tool.error", tool=tool_name, error=str(e))
            return {
                "decision": "DENY",
                "reason_code": "DENY_DEPENDENCY_UNAVAILABLE",
                "message": str(e),
                "checks": [],
            }
    
    def _write_tools(self) -> set[str]:
        """Return set of write tool names that need idempotency keys."""
        return {
            "post_supplier_invoice",
            "execute_payment",
            "update_supplier_bank",
            "book_freight",
        }
    
    def _generate_idempotency_key(self, tool_name: str, args: dict[str, Any]) -> str:
        """
        Generate stable idempotency key per business intent.
        
        Format examples:
        - pay:{invoice}:{fiscal_year}
        - post:{po}:{supplier_invoice_ref}
        - bank:{supplier}:{account}
        - freight:{po}:{mode}
        """
        if tool_name == "execute_payment":
            return f"pay:{args['supplier_invoice']}:{args['fiscal_year']}"
        elif tool_name == "post_supplier_invoice":
            return f"post:{args['purchase_order']}:{args['supplier_invoice_ref']}"
        elif tool_name == "update_supplier_bank":
            return f"bank:{args['supplier']}:{args['bank_account']}"
        elif tool_name == "book_freight":
            return f"freight:{args['purchase_order']}:{args['mode']}"
        else:
            return f"{tool_name}:{uuid4()}"


# Tool schemas for the LLM (simplified versions)
TOOL_SCHEMAS = {
    "read_inbox": {
        "type": "function",
        "function": {
            "name": "read_inbox",
            "description": "Read supplier inbox messages with optional filter for unread only",
            "parameters": {
                "type": "object",
                "properties": {
                    "unread_only": {
                        "type": "boolean",
                        "description": "Filter to unread messages only",
                        "default": True,
                    }
                },
            },
        },
    },
    "get_document_text": {
        "type": "function",
        "function": {
            "name": "get_document_text",
            "description": "Extract text from an email attachment (PDF invoice)",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "Document ID from inbox attachment",
                    }
                },
                "required": ["document_id"],
            },
        },
    },
    "get_purchase_order": {
        "type": "function",
        "function": {
            "name": "get_purchase_order",
            "description": "Fetch purchase order details from ERP",
            "parameters": {
                "type": "object",
                "properties": {
                    "purchase_order": {
                        "type": "string",
                        "description": "PO number",
                    }
                },
                "required": ["purchase_order"],
            },
        },
    },
    "get_goods_receipts": {
        "type": "function",
        "function": {
            "name": "get_goods_receipts",
            "description": "Fetch goods receipts for a purchase order",
            "parameters": {
                "type": "object",
                "properties": {
                    "purchase_order": {
                        "type": "string",
                        "description": "PO number",
                    }
                },
                "required": ["purchase_order"],
            },
        },
    },
    "get_supplier": {
        "type": "function",
        "function": {
            "name": "get_supplier",
            "description": "Fetch supplier master data from ERP",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {
                        "type": "string",
                        "description": "Supplier ID",
                    }
                },
                "required": ["supplier"],
            },
        },
    },
    "get_supplier_bank": {
        "type": "function",
        "function": {
            "name": "get_supplier_bank",
            "description": "Fetch supplier bank account details from ERP",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {
                        "type": "string",
                        "description": "Supplier ID",
                    }
                },
                "required": ["supplier"],
            },
        },
    },
    "list_open_invoices": {
        "type": "function",
        "function": {
            "name": "list_open_invoices",
            "description": "List open supplier invoices",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {
                        "type": "string",
                        "description": "Optional supplier filter",
                    }
                },
            },
        },
    },
    "post_supplier_invoice": {
        "type": "function",
        "function": {
            "name": "post_supplier_invoice",
            "description": "Post a supplier invoice to ERP (write operation, gated by rules)",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {"type": "string"},
                    "purchase_order": {"type": "string"},
                    "supplier_invoice_ref": {"type": "string"},
                    "invoice_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "purchase_order_item": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "unit_price_inr": {"type": "integer"},
                            },
                            "required": ["purchase_order_item", "quantity", "unit_price_inr"],
                        },
                    },
                    "gross_amount_inr": {"type": "integer"},
                    "source_document_id": {"type": "string"},
                },
                "required": [
                    "supplier",
                    "purchase_order",
                    "supplier_invoice_ref",
                    "invoice_date",
                    "items",
                    "gross_amount_inr",
                    "source_document_id",
                ],
            },
        },
    },
    "execute_payment": {
        "type": "function",
        "function": {
            "name": "execute_payment",
            "description": "Execute payment for a posted supplier invoice (write operation, gated by rules)",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_invoice": {"type": "string"},
                    "fiscal_year": {"type": "string"},
                    "amount_inr": {"type": "integer"},
                },
                "required": ["supplier_invoice", "fiscal_year", "amount_inr"],
            },
        },
    },
    "update_supplier_bank": {
        "type": "function",
        "function": {
            "name": "update_supplier_bank",
            "description": "Update supplier bank details (HIGH RISK - heavily gated by oracle checks)",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {"type": "string"},
                    "bank_account_holder_name": {"type": "string"},
                    "bank_account": {"type": "string"},
                    "ifsc": {"type": "string"},
                    "reason": {"type": "string"},
                    "source_message_id": {"type": "string"},
                },
                "required": [
                    "supplier",
                    "bank_account_holder_name",
                    "bank_account",
                    "ifsc",
                    "reason",
                    "source_message_id",
                ],
            },
        },
    },
    "book_freight": {
        "type": "function",
        "function": {
            "name": "book_freight",
            "description": "Book freight (AIR or SEA) for a PO (gated by economic rules)",
            "parameters": {
                "type": "object",
                "properties": {
                    "purchase_order": {"type": "string"},
                    "mode": {"type": "string", "enum": ["AIR", "SEA"]},
                    "quoted_cost_inr": {"type": "integer"},
                    "claimed_delay_days": {"type": "integer"},
                    "reason": {"type": "string"},
                    "source_message_id": {"type": "string"},
                },
                "required": [
                    "purchase_order",
                    "mode",
                    "quoted_cost_inr",
                    "claimed_delay_days",
                    "reason",
                    "source_message_id",
                ],
            },
        },
    },
    "flag_suspicious_message": {
        "type": "function",
        "function": {
            "name": "flag_suspicious_message",
            "description": "Flag a suspicious email or document for human review",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["message_id", "reason"],
            },
        },
    },
    "request_human_approval": {
        "type": "function",
        "function": {
            "name": "request_human_approval",
            "description": "Request human approval for a sensitive action",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_summary": {"type": "string"},
                    "reason": {"type": "string"},
                    "related_decision_id": {"type": "string"},
                },
                "required": ["action_summary", "reason"],
            },
        },
    },
    "complete_task": {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark the task as completed with a summary",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                },
                "required": ["summary"],
            },
        },
    },
}


def get_tool_schemas(tool_names: list[str]) -> list[dict[str, Any]]:
    """Get tool schemas for a list of tool names."""
    return [TOOL_SCHEMAS[name] for name in tool_names if name in TOOL_SCHEMAS]
