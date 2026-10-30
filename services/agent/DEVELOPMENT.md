# Agent Service Development Guide

## Quick Start for Development

### 1. Prerequisites

```powershell
# Check Python version
python --version  # Should be 3.12+

# Check Ollama
ollama --version

# Pull model
ollama pull qwen2.5:7b
```

### 2. Setup

```powershell
cd services/agent

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Edit .env with your settings
notepad .env
```

### 3. Run Service

```powershell
# Start service
uvicorn app.main:app --reload --port 8003

# In another terminal, test
curl http://localhost:8003/v1/health
```

## Project Structure

```
services/agent/
├── app/
│   ├── main.py              # FastAPI app
│   ├── api/                 # API routes
│   │   ├── health.py        # Health check
│   │   ├── tasks.py         # Task CRUD
│   │   └── model.py         # Model management
│   ├── core/                # Core logic
│   │   ├── agent.py         # State machine ⭐
│   │   ├── llm.py           # Ollama client ⭐
│   │   ├── tools.py         # Tool executor ⭐
│   │   ├── replan.py        # Replanning logic ⭐
│   │   ├── memory.py        # Memory management
│   │   ├── events.py        # Event emission
│   │   └── config.py        # Settings
│   └── db/                  # Database
│       ├── models.py        # SQLAlchemy models
│       └── __init__.py      # Session factory
├── tests/                   # Tests
│   ├── test_llm.py
│   ├── test_tools.py
│   ├── test_replan.py       # ⭐ Key security tests
│   └── test_agent.py
├── eval/                    # Model evaluation
│   └── model_eval.py
├── traces/                  # Recorded demos
└── scripts/                 # Helper scripts
```

⭐ = Most important files

## Development Workflow

### Day 1: Foundation ✅
- [x] Project structure
- [x] Ollama client
- [x] Tool schemas
- [x] Basic FastAPI app

### Day 2: Core Logic (Current)
- [ ] Database setup
- [ ] State machine implementation
- [ ] Task creation with lease
- [ ] Read tools integration
- [ ] Model evaluation

### Day 3: Replanning & Security
- [ ] Replanning logic (critical!)
- [ ] Approval handling
- [ ] Memory management
- [ ] Event emission
- [ ] Trace recording

### Day 4: Integration
- [ ] Connect to gateway
- [ ] Full workflow testing
- [ ] Error handling
- [ ] Replay mode

### Day 5-7: Polish & Demo
- [ ] Model selection
- [ ] Golden trace recording
- [ ] Documentation
- [ ] Rehearsal

## Key Concepts

### State Machine

```
RECEIVED → PLANNING → EXECUTING ⇄ REPLANNING → COMPLETED
                ↓
           AWAITING_APPROVAL
                ↓
            EXECUTING
```

### Budgets (Hard Limits)

- `max_steps`: 12
- `max_tool_calls`: 20
- `max_llm_calls`: 30
- `max_replans`: 2
- `max_wall_seconds`: 180

### Replanning (Security Feature)

When gateway says DENY/HOLD:
1. Read `reason_code`
2. Choose from `safe_alternatives`
3. **NEVER retry same business intent**
4. Execute safe action (flag, request_approval, skip, abort)

### Tool Calling Flow

```
LLM → plan_action()
  ↓
Validate args locally
  ↓
Call gateway with lease
  ↓
Gateway decides (ALLOW/HOLD/DENY)
  ↓
Agent responds:
  - ALLOW → use result, continue
  - HOLD → request approval
  - DENY → replan (never retry!)
```

## Testing

```powershell
# All tests
pytest tests/ -v

# Specific test
pytest tests/test_replan.py -v

# With coverage
pytest --cov=app tests/

# Watch mode
ptw -- -v
```

### Key Tests

1. **test_replan.py** - Critical security tests
2. **test_tools.py** - Idempotency keys
3. **test_agent.py** - State machine transitions
4. **test_llm.py** - Ollama integration

## Model Evaluation

```powershell
# Run evaluation harness
python eval/model_eval.py

# Or use script
.\scripts\run_eval.ps1
```

This tests:
- Tool selection accuracy
- BEC refusal behavior
- Latency
- Schema compliance

## Debugging

### Check Ollama

```powershell
# Is it running?
curl http://localhost:11434/api/tags

# Test model
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "What is 2+2?",
  "stream": false
}'
```

### Check Logs

```powershell
# Service logs (structured JSON)
# Look for:
# - agent.llm.call
# - agent.tool.executed
# - agent.replanned
```

### Common Issues

1. **Ollama timeout**: Increase `OLLAMA_TIMEOUT` in .env
2. **Model not found**: Run `ollama pull qwen2.5:7b`
3. **Gateway unavailable**: Service uses mock lease for testing
4. **Context too large**: Trim tool outputs, reduce tool list

## Environment Variables

Key settings in `.env`:

```bash
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TEMPERATURE=0.2

# Budgets
MAX_STEPS=12
MAX_TOOL_CALLS=20
MAX_LLM_CALLS=30

# Mode
AGENT_MODE=L0  # L0=live, L3=replay

# Gateway
GATEWAY_URL=http://localhost:8000
AGENT_SERVICE_TOKEN=your-token
```

## API Endpoints

```powershell
# Health check
curl http://localhost:8003/v1/health

# Create task
curl -X POST http://localhost:8003/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "process_supplier_inbox"}'

# Get task status
curl http://localhost:8003/v1/tasks/{task_id}

# Get trace
curl http://localhost:8003/v1/tasks/{task_id}/trace

# Model info
curl http://localhost:8003/v1/model
```

## Next Steps

1. **Implement database migrations** (Alembic)
2. **Complete state machine** in `app/core/agent.py`
3. **Add event emission** to gateway
4. **Test replanning** with mocked gateway
5. **Run model evaluation**

## Resources

- Master Spec: `docs/MASTER_SPEC.md`
- Prompt: `docs/03-Prompt-Harshita.md`
- Tool Contracts: Section 9 of spec
- Gateway API: Section 10 of spec

## Questions?

Ask in team chat or check the spec!
