# Quick Start - Run Agent Service Locally

## Step 1: Install Ollama (The AI Model)

### Windows
1. Go to https://ollama.com/download
2. Download Windows installer
3. Run the installer
4. Open PowerShell and run:
   ```powershell
   ollama pull qwen2.5:7b
   ```
   This downloads the AI model (takes a few minutes)

### Verify Ollama is Running
```powershell
curl http://localhost:11434/api/tags
```
You should see a list of models including qwen2.5:7b

---

## Step 2: Setup Python Environment

```powershell
# 1. Navigate to your project
cd "C:\Users\Harshitha\OneDrive\Desktop\py projects\agentshield\services\agent"

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
.\venv\Scripts\activate

# You should see (venv) in your prompt now

# 4. Install dependencies
pip install -e ".[dev]"
```

---

## Step 3: Configure Environment

```powershell
# 1. Copy example config
cp .env.example .env

# 2. Open .env in notepad
notepad .env
```

### Edit these lines in .env:

```bash
# Change this line:
DATABASE_URL=postgresql://agent_svc:agent_password@localhost:5432/agentshield

# To (for now, until database is ready):
DATABASE_URL=sqlite:///./test.db

# Keep these as-is for now:
JWT_SECRET=demo-secret-change-in-production
AGENT_SERVICE_TOKEN=demo-agent-token

# These should work as-is:
GATEWAY_URL=http://localhost:8000
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

Save and close.

---

## Step 4: Run the Service

```powershell
# Make sure you're in services/agent with venv activated
uvicorn app.main:app --reload --port 8003
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8003
INFO:     Application startup complete
```

---

## Step 5: Test It Works

### Test 1: Health Check

Open a **new PowerShell window** (keep the first one running) and run:

```powershell
curl http://localhost:8003/v1/health
```

**Expected result:**
```json
{
  "status": "healthy",
  "service": "agent",
  "checks": {
    "ollama": "pass"
  }
}
```

✅ If you see this, your service is working!

❌ If ollama shows "fail", check Ollama is running

---

### Test 2: Check Model Info

```powershell
curl http://localhost:8003/v1/model
```

**Expected result:**
```json
{
  "model": "qwen2.5:7b",
  "host": "http://localhost:11434",
  "mode": "L0",
  "temperature": 0.2
}
```

---

### Test 3: Create a Task

```powershell
curl -X POST http://localhost:8003/v1/tasks -H "Content-Type: application/json" -d '{\"goal\": \"process_supplier_inbox\"}'
```

**Expected result:**
```json
{
  "task_id": "some-uuid",
  "status": "RECEIVED",
  "goal": "process_supplier_inbox",
  "created_at": "2026-10-30T..."
}
```

Note: This will show a warning about "Gateway not available, using mock lease" - that's OK! You're testing standalone.

---

## Step 6: Run Tests

```powershell
# In the services/agent directory with venv activated
pytest tests/ -v
```

You should see tests passing:
```
test_llm.py::test_ollama_client_initialization PASSED
test_tools.py::test_tool_schemas_exist PASSED
test_tools.py::test_idempotency_key_generation PASSED
test_replan.py::test_bank_name_mismatch_replan PASSED
...
```

---

## Troubleshooting

### Problem: "Ollama connection failed"
**Solution:** 
1. Check Ollama is running: Open Ollama from Start Menu
2. Test: `curl http://localhost:11434/api/tags`
3. Pull model again: `ollama pull qwen2.5:7b`

### Problem: "ModuleNotFoundError"
**Solution:**
```powershell
# Make sure venv is activated (you see (venv) in prompt)
.\venv\Scripts\activate

# Reinstall
pip install -e ".[dev]"
```

### Problem: "Port 8003 already in use"
**Solution:**
```powershell
# Use a different port
uvicorn app.main:app --reload --port 8004
```

### Problem: "Database error"
**Solution:** 
Make sure .env has `DATABASE_URL=sqlite:///./test.db` for local testing

---

## What Each Test Means

- ✅ **Health Check** - Service is running, Ollama connected
- ✅ **Model Info** - Configuration correct
- ✅ **Create Task** - API works (will need gateway for full flow)
- ✅ **Tests Pass** - All logic is correct

---

## You're Done! 🎉

Your agent service is:
- ✅ Running locally
- ✅ Connected to Ollama
- ✅ Passing tests
- ✅ Ready to integrate with team services

---

## Optional: Run Model Evaluation

If you want to test which AI model works best:

```powershell
python eval/model_eval.py
```

This takes 5-10 minutes and shows which model is best for the demo.

---

## Next: Team Integration

When team services are ready:
1. **Gateway** (Chandan) - Update GATEWAY_URL in .env
2. **Database** (Pavan) - Update DATABASE_URL in .env
3. **Full testing** - All services together
