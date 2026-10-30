# Test Commands - Copy & Paste to Verify Everything Works

## 1. Setup (One Time)

```powershell
# Navigate to agent directory
cd "C:\Users\Harshitha\OneDrive\Desktop\py projects\agentshield\services\agent"

# Create virtual environment
python -m venv venv

# Activate it (you'll see (venv) in prompt)
.\venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy config
cp .env.example .env
```

### Edit .env file
Open `.env` in notepad and change this line:
```
DATABASE_URL=sqlite:///./test.db
```

---

## 2. Check Ollama (Every Time Before Running)

```powershell
# Test if Ollama is running
curl http://localhost:11434/api/tags
```

✅ Should show list of models  
❌ If not, open Ollama from Start Menu, then run:
```powershell
ollama pull qwen2.5:7b
```

---

## 3. Start Service

```powershell
# Make sure you're in services/agent with (venv) active
uvicorn app.main:app --reload --port 8003
```

✅ You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8003
INFO:     Application startup complete
agent.startup | service=agent | ollama_ready
```

**Keep this window open!** Open a NEW PowerShell for testing.

---

## 4. Test Service (Run in New Window)

### Test 1: Health Check
```powershell
curl http://localhost:8003/v1/health
```

✅ **Good response:**
```json
{
  "status": "healthy",
  "checks": {
    "ollama": "pass"
  }
}
```

❌ If ollama shows "fail", check Ollama is running

---

### Test 2: Root Endpoint
```powershell
curl http://localhost:8003/
```

✅ **Good response:**
```json
{
  "service": "agentshield-agent",
  "version": "0.1.0",
  "status": "running",
  "mode": "L0"
}
```

---

### Test 3: Model Info
```powershell
curl http://localhost:8003/v1/model
```

✅ **Good response:**
```json
{
  "model": "qwen2.5:7b",
  "host": "http://localhost:11434",
  "mode": "L0",
  "temperature": 0.2
}
```

---

### Test 4: Create Task
```powershell
curl -X POST http://localhost:8003/v1/tasks -H "Content-Type: application/json" -d '{\"goal\":\"process_supplier_inbox\"}'
```

✅ **Good response:**
```json
{
  "task_id": "some-uuid-here",
  "status": "RECEIVED",
  "goal": "process_supplier_inbox",
  "created_at": "2026-10-30T..."
}
```

Note: Will show warning "using mock lease" - that's OK for standalone testing!

---

### Test 5: Get Task Status

Copy the `task_id` from previous test, then:
```powershell
# Replace YOUR_TASK_ID with the actual ID
curl http://localhost:8003/v1/tasks/YOUR_TASK_ID
```

✅ **Good response:**
```json
{
  "task_id": "...",
  "status": "COMPLETED" or "FAILED",
  "current_step": 2
}
```

---

## 5. Run Tests

```powershell
# Make sure you're in services/agent with venv active
pytest tests/ -v
```

✅ **Good result:**
```
tests/test_llm.py::test_ollama_client_initialization PASSED
tests/test_tools.py::test_tool_schemas_exist PASSED
tests/test_tools.py::test_idempotency_key_generation PASSED
tests/test_replan.py::test_bank_name_mismatch_replan PASSED
tests/test_replan.py::test_price_variance_replan PASSED
tests/test_replan.py::test_hold_needs_approval_replan PASSED
tests/test_replan.py::test_lease_denied_abort PASSED
tests/test_replan.py::test_duplicate_payment_skip PASSED
tests/test_agent.py::test_agent_initialization PASSED

======= 9 passed in 0.5s =======
```

---

## 6. Optional: Run Model Evaluation

```powershell
python eval/model_eval.py
```

This takes 5-10 minutes and tests which AI model works best.

✅ **Good result:**
```
=== MODEL EVALUATION RESULTS ===

Model: qwen2.5:7b
  Available: True
  Tool Selection: 80%
  BEC Refusal: 100/100
  Avg Latency: 850ms

RECOMMENDATION: qwen2.5:7b
Reason: Best balance of accuracy, security, and speed
```

---

## Quick Checklist - "Is My Service Working?"

Run these in order:

1. ✅ `curl http://localhost:11434/api/tags` - Ollama ready
2. ✅ `uvicorn app.main:app --reload --port 8003` - Service starts
3. ✅ `curl http://localhost:8003/v1/health` - Shows "healthy"
4. ✅ `pytest tests/ -v` - All tests pass

**If all 4 work, you're 100% ready!**

---

## Troubleshooting

### "Connection refused" on port 11434
→ Ollama not running. Open Ollama from Start Menu.

### "Module not found"
→ Activate venv: `.\venv\Scripts\activate`

### "Port 8003 already in use"
→ Stop previous service (Ctrl+C in that window) or use different port

### Tests fail with "gateway not available"
→ That's OK for now! Gateway comes from Chandan's service.

### "Ollama timeout"
→ Model might be slow. Wait 2 minutes or try smaller model:
```powershell
ollama pull qwen2.5:4b
# Then edit .env: OLLAMA_MODEL=qwen2.5:4b
```

---

## What Each Test Proves

| Test | What It Proves |
|------|----------------|
| Health check | Service is running, Ollama connected |
| Model info | Configuration correct |
| Create task | API works, can create tasks |
| Task status | Background execution works |
| Pytest tests | Logic is correct |
| Model eval | Can pick best model for demo |

---

## Screenshot This for Team

Take screenshots showing:
1. `curl http://localhost:8003/v1/health` showing "healthy"
2. `pytest tests/ -v` showing all tests passed
3. Service running with "Application startup complete"

This proves your service is working!

---

## Stop Service

In the window running uvicorn:
```
Press Ctrl+C
```

To deactivate venv:
```powershell
deactivate
```

---

## Next Time You Work

```powershell
cd "C:\Users\Harshitha\OneDrive\Desktop\py projects\agentshield\services\agent"
.\venv\Scripts\activate
uvicorn app.main:app --reload --port 8003
```

That's it!
