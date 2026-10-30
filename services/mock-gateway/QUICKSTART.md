# Mock Gateway Quick Start

Get the mock gateway running in 2 minutes.

## Step 1: Setup

```bash
cd services/mock-gateway
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Run

```bash
python app/main.py
```

You should see:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

## Step 3: Test

In a new terminal:

```bash
cd services/mock-gateway
venv\Scripts\activate
pip install requests  # if not already installed
python test_mock_gateway.py
```

Expected output:
```
============================================================
Mock Gateway Test Suite
============================================================

Testing health endpoint...
  Status: 200
  Response: {'status': 'healthy', 'service': 'mock-gateway'}
✅ Health check passed

Testing lease issuance...
  Status: 200
  Lease ID: lease-abc123def456
  Signature: sig-xyz789abc123def456
✅ Lease issuance passed

Testing tool call (ALLOW)...
  Status: 200
  Decision: ALLOW
  Message: Operation allowed by mock gateway
✅ ALLOW decision passed

Testing tool call (HOLD)...
  Status: 200
  Decision: HOLD
  Message: Amount ₹5,00,000 exceeds approval threshold ₹2,00,000
  Approval ID: appr-abc123def456
✅ HOLD decision passed

Testing approval polling for appr-abc123def456...
  Status: 200
  Approval Status: pending
  Waiting 11 seconds for auto-approval...
  Approval Status: approved
  Decision: ALLOW
✅ Approval polling passed

Testing event reception...
  Status: 200
  Response: {'status': 'received', 'event_type': 'task.created'}
✅ Event reception passed

============================================================
✅ All tests passed!
============================================================
```

## Step 4: Integrate with Agent

Update `services/agent/.env`:

```bash
GATEWAY_URL=http://localhost:8001
```

Now restart the agent service and it will use the mock gateway!

## Testing Different Scenarios

### Scenario 1: Test DENY Decision

Edit `.env`:
```
HIGH_RISK_TOOLS=read_file,execute_payment
```

Restart mock gateway. Now `read_file` calls will be DENIED.

### Scenario 2: Test Lower Threshold

Edit `.env`:
```
APPROVAL_THRESHOLD_INR=50000
```

Restart mock gateway. Now amounts > ₹50,000 trigger HOLD.

### Scenario 3: Test All DENY

Edit `.env`:
```
MOCK_DECISION=DENY
```

Restart mock gateway. All tool calls will be DENIED (tests safe alternatives).

## Troubleshooting

**Port already in use:**
```bash
# Change PORT in .env
PORT=8002
```

**Agent can't connect:**
- Make sure mock gateway is running
- Check agent's .env has correct GATEWAY_URL
- Try `curl http://localhost:8001/health`

**Tests timeout:**
- Check if mock gateway is running on correct port
- Ensure no firewall/antivirus blocking localhost

## Next Steps

Once the mock gateway is working:
1. Create a task via the Agent API
2. Watch the agent interact with mock gateway
3. See ALLOW/DENY/HOLD decisions in action
4. Test approval polling with high-amount tool calls

See `README.md` for full documentation.
