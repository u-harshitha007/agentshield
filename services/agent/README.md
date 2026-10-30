# AgentShield Agent Runtime

**Owner:** Harshita  
**Purpose:** Real AI agent with local Ollama that processes supply chain tasks with security controls

## What This Is

This service runs the actual agentic AI that:
- Processes supplier inbox messages
- Reads invoice PDFs
- Performs three-way matching (PO vs GR vs Invoice)
- Posts invoices and executes payments
- Handles logistics disruptions
- **ALL through the gateway** - no direct ERP access

## Key Features

✅ **Local AI** - Uses Ollama (open-weight models), no cloud APIs  
✅ **Policy-Aware** - When gateway says DENY/HOLD, agent replans safely  
✅ **Never Retries** - After a DENY, picks safe alternatives (flag, approve, skip)  
✅ **Structured Tools** - 14 typed tools with schema validation  
✅ **Full Tracing** - Every LLM call, tool call, decision tracked  
✅ **Replay Mode** - Record successful runs, replay for demos  

## Architecture

```
┌─────────────┐
│   Ollama    │ (on host, local model)
└──────┬──────┘
       │
┌──────▼──────────────────────────┐
│  Agent Service :8003            │
│                                 │
│  ┌─────────────────────────┐   │
│  │  LLM Client             │   │
│  │  (app/core/llm.py)      │   │
│  └────────┬────────────────┘   │
│           │                     │
│  ┌────────▼────────────────┐   │
│  │  Planner / State Machine│   │
│  │  (app/core/agent.py)    │   │
│  └────────┬────────────────┘   │
│           │                     │
│  ┌────────▼────────────────┐   │
│  │  Tool Executor          │   │
│  │  (app/core/tools.py)    │   │
│  └────────┬────────────────┘   │
│           │                     │
│  ┌────────▼────────────────┐   │
│  │  Replanning Logic       │   │
│  │  (app/core/replan.py)   │   │
│  └─────────────────────────┘   │
└─────────────┬───────────────────┘
              │
              │ All tool calls go through gateway
              │
     ┌────────▼────────┐
     │  Gateway :8000  │
     └─────────────────┘
```

## Development Status

### ✅ Done (Day 1 - Current)
- [x] Project structure
- [x] Ollama client with tool calling
- [x] Tool schemas and executor
- [x] Health check
- [x] Configuration management
- [x] Basic FastAPI app

### 🚧 In Progress (Day 2)
- [ ] Database models and migrations
- [ ] Task creation with lease request
- [ ] State machine implementation
- [ ] Read tools integration
- [ ] Model evaluation harness

### 📋 TODO (Day 3-4)
- [ ] Full planner with budgets
- [ ] Replanning logic
- [ ] Approval handling
- [ ] Memory management
- [ ] Tracing and events
- [ ] Replay mode

### 🎯 TODO (Day 5-7)
- [ ] Model evaluation report
- [ ] Prompt hardening
- [ ] Record golden trace
- [ ] Integration testing
- [ ] Documentation

## Quick Start

### Prerequisites
1. **Ollama installed** on host machine
2. **Model downloaded**: `ollama pull qwen2.5:7b`
3. **PostgreSQL** running (via docker-compose)

### Run Locally

```bash
cd services/agent

# Install dependencies
pip install -e ".[dev]"

# Copy env file
cp .env.example .env

# Run migrations (TODO)
# alembic upgrade head

# Run service
uvicorn app.main:app --reload --port 8003
```

### Test Ollama Connection

```bash
# Check health
curl http://localhost:8003/v1/health

# Expected response:
{
  "status": "healthy",
  "checks": {
    "ollama": "pass"
  }
}
```

## Tool Calling Flow

1. **LLM Plans** - Model suggests next tool and args
2. **Validate** - Schema validation locally
3. **Call Gateway** - POST /v1/tool-calls with lease
4. **Gateway Decides** - ALLOW/HOLD/DENY based on rules
5. **Agent Responds**:
   - ALLOW → use result, continue
   - HOLD → request approval, wait
   - DENY → replan with safe alternatives

## Replanning Examples

```python
# DENY_BANK_NAME_MISMATCH
# Agent does: flag_suspicious_message + request_human_approval
# Agent NEVER retries update_supplier_bank

# DENY_PRICE_VARIANCE
# Agent does: flag_suspicious_message
# Does NOT post invoice

# HOLD_BANK_COOLING_OFF
# Agent does: request_human_approval
# Waits for approval, then retries
```

## Testing

```bash
# Unit tests
pytest tests/

# Specific test
pytest tests/test_llm.py -v

# With coverage
pytest --cov=app tests/
```

## Environment Variables

Key variables:
- `OLLAMA_HOST` - Ollama endpoint (default: http://host.docker.internal:11434)
- `OLLAMA_MODEL` - Model name (default: qwen2.5:7b)
- `GATEWAY_URL` - Gateway endpoint
- `AGENT_MODE` - L0 (live) or L3 (replay)
- `MAX_STEPS` - Budget limit (default: 12)

## Events Emitted

- `agent.task.created`
- `agent.task.completed`
- `agent.task.failed`
- `agent.llm.call`
- `agent.tool.called`
- `agent.replanned`
- `system.mode.changed`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/health` | GET | Health check |
| `/v1/tasks` | POST | Create task |
| `/v1/tasks/{id}` | GET | Get task status |
| `/v1/tasks/{id}/trace` | GET | Get execution trace |
| `/v1/tasks/{id}/cancel` | POST | Cancel task |
| `/v1/model` | GET | Get model info |
| `/v1/model` | POST | Set mode (admin) |

## Notes

- **Model is NOT a security control** - Gateway enforces all rules
- **External content is untrusted** - PDFs/emails never treated as instructions
- **No retries after DENY** - This is a security invariant
- **Small context window** - Trim tool outputs, keep tool lists small (≤6)
- **Low temperature** - 0.2 for reliability with small models

## Team Integration

- **Depends on**: Gateway (Chandan), Contracts (Pavan)
- **Used by**: Web UI (Yogesh), E2E tests (Pavan)
- **Coordinate with**: Everyone for finale scenarios

## Questions?

Ask Harshita or check:
- `docs/MASTER_SPEC.md` Sections 9, 10, 11, 13
- Prompt 3 (03-Prompt-Harshita.md)
