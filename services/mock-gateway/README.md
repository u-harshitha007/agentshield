# Mock Gateway Service

A minimal Gateway implementation for testing the Agent Runtime without requiring the full Gateway module.

## Purpose

This mock service provides the essential endpoints that the Agent Runtime needs to function:
- **POST /v1/tasks** - Issue capability leases
- **POST /v1/tool-calls** - Evaluate tool calls (ALLOW/DENY/HOLD)
- **GET /v1/approvals/{id}** - Check approval status
- **POST /v1/events** - Receive audit events (no-op)

## Quick Start

### 1. Install Dependencies

```bash
cd services/mock-gateway
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env
# Edit .env to customize behavior
```

### 3. Run

```bash
python app/main.py
```

The service will start on `http://localhost:8001` (configurable via PORT env var).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8001 | Port to run the service on |
| `MOCK_DECISION` | ALLOW | Default decision: ALLOW, DENY, or HOLD |
| `HIGH_RISK_TOOLS` | execute_payment,delete_supplier | Tools that trigger DENY |
| `APPROVAL_THRESHOLD_INR` | 200000 | Amount threshold for HOLD (₹2 lakh) |

## Decision Logic

The mock gateway evaluates tool calls with this logic:

1. **DENY** if tool is in `HIGH_RISK_TOOLS` list
2. **HOLD** if extracted amount > `APPROVAL_THRESHOLD_INR`
3. Otherwise, returns `MOCK_DECISION` (configurable)

### Amount Extraction

The mock tries to extract amounts from these arg keys:
- `amount`
- `amount_inr`
- `value`
- `payment_amount`

Handles formats: `25000`, `"25000"`, `"₹25,000"`

## Approval Polling

When a HOLD decision is returned, an `approval_id` is generated. You can poll:

```
GET /v1/approvals/{approval_id}
```

**Mock Behavior:** Auto-approves after 10 seconds for testing.

## Testing Scenarios

### Scenario 1: All ALLOW
```bash
# .env
MOCK_DECISION=ALLOW
```

All tool calls will be allowed.

### Scenario 2: High-Risk Tool
```bash
# .env
MOCK_DECISION=ALLOW
HIGH_RISK_TOOLS=execute_payment,delete_supplier
```

Tools `execute_payment` and `delete_supplier` will be DENIED, others ALLOWED.

### Scenario 3: Amount Threshold
```bash
# .env
MOCK_DECISION=ALLOW
APPROVAL_THRESHOLD_INR=200000
```

Tool calls with amount > ₹2,00,000 will trigger HOLD with approval_id.

### Scenario 4: All DENY
```bash
# .env
MOCK_DECISION=DENY
```

All tool calls will be denied (useful for testing safe alternatives).

## Integration with Agent

Update the Agent's `.env` to point to the mock gateway:

```bash
# services/agent/.env
GATEWAY_URL=http://localhost:8001
```

Then start the agent:

```bash
cd services/agent
uvicorn app.main:app --reload --port 8003
```

Now you can create tasks via the Agent API and see it interact with the mock gateway.

## API Documentation

Once running, visit:
- **Swagger UI:** http://localhost:8001/docs
- **Health Check:** http://localhost:8001/health

## Limitations

This is a **testing mock only**:
- ✅ Supports ALLOW/DENY/HOLD decisions
- ✅ Generates approval IDs and lease signatures
- ✅ Auto-approval after 10 seconds
- ❌ No policy engine
- ❌ No database persistence
- ❌ No Oracle integrations
- ❌ No audit trail storage

For production use, integrate with Chandan's full Gateway module.

## Development

The mock gateway is a single-file FastAPI app (`app/main.py`) for simplicity. Feel free to extend it for your testing needs.

## Troubleshooting

**Agent can't reach gateway:**
- Check GATEWAY_URL in agent's .env
- Ensure mock gateway is running on the configured PORT
- Check firewall/antivirus blocking localhost connections

**Tool calls still fail:**
- Check mock gateway logs for errors
- Verify tool_args contain expected keys for amount extraction
- Try DEFAULT_DECISION=ALLOW to rule out decision logic

**Approval polling doesn't work:**
- Wait 10 seconds (mock auto-approves)
- Check approval_id is returned in HOLD response
- Verify agent is polling GET /v1/approvals/{id}
