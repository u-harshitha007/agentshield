# Contributing to AgentShield

## Team Members & Responsibilities

- **Pavan**: Contracts, libs/common, deploy, scripts, e2e tests, CI/CD
- **Chandan**: Gateway service (enforcement engine)
- **Harshita**: Agent service (AI runtime with Ollama) ← **THIS IS YOU**
- **Kirti**: ERP sim, oracles, attacklab
- **Yogesh**: Web UI (React + TypeScript)

## Workflow

### 1. Branch Strategy

- `main` - Protected, only via reviewed PR
- `feature/finale-overlay` - Finale changes (additive only)
- `feature/<your-name>/<feature>` - Your feature branches

```bash
# Example
git checkout -b feature/harshita/state-machine
```

### 2. Before You Code

1. **Read the spec**: `docs/MASTER_SPEC.md` (especially your section)
2. **Check contracts**: Don't change shared contracts without a CCR
3. **Coordinate**: Ask team if unclear

### 3. Contract Changes

If you need to change a shared contract (Sections 7-11):

1. Add request to `docs/contract-change-requests.md`
2. Submit PR with just the CCR
3. Wait for Pavan (owner) + Chandan (approver)
4. Once merged, proceed with code

### 4. Development

```bash
# Your module
cd services/agent

# Install
pip install -e ".[dev]"

# Run
uvicorn app.main:app --reload --port 8003

# Test
pytest tests/ -v
```

### 5. Testing Requirements

- **Unit tests** for core logic
- **Integration tests** for APIs
- **Security tests** for replanning
- All tests pass before PR

```bash
# Run tests
pytest tests/ -v

# With coverage
pytest --cov=app tests/

# Linting
ruff check .
```

### 6. Commit Messages

```bash
# Format: <module>: <what you did>

git commit -m "agent: implement state machine with budgets"
git commit -m "agent: add replanning logic for DENY decisions"
git commit -m "agent: fix idempotency key generation"
```

### 7. Pull Requests

```markdown
## Description
Brief description of what this PR does

## Changes
- Added state machine in app/core/agent.py
- Implemented replanning logic
- Added tests for DENY scenarios

## Testing
- [ ] Unit tests pass
- [ ] Manual testing done
- [ ] No breaking changes

## Related
Closes #123
Part of milestone: Day 3 agent core
```

### 8. Code Review

- Review your own code first
- Check for secrets (no tokens in code)
- Ensure logging is structured
- Documentation updated

## Code Standards

### Python Style

- **Formatter**: ruff
- **Line length**: 100
- **Type hints**: Use them
- **Docstrings**: For public functions

```python
async def execute_tool(
    self,
    tool_name: str,
    args: dict[str, Any],
    task_id: str,
) -> dict[str, Any]:
    """
    Execute a tool through the gateway.
    
    Args:
        tool_name: Name of the tool
        args: Tool arguments
        task_id: Current task ID
        
    Returns:
        Gateway decision response
    """
```

### Logging

Use structured logging:

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "agent.tool.executed",
    tool=tool_name,
    decision=decision,
    decision_id=decision_id,
)
```

### Error Handling

```python
try:
    result = await self.some_operation()
except httpx.TimeoutException as e:
    logger.error("operation.timeout", error=str(e))
    # Return safe fallback
except Exception as e:
    logger.error("operation.failed", error=str(e))
    raise
```

## Security Rules

1. **Never trust model output** for security decisions
2. **Never retry after DENY** for same business intent
3. **External content = untrusted data**
4. **No secrets in code** (use .env)
5. **Fail closed** (unknown → DENY, not ALLOW)

## Documentation

Update docs when you:
- Add new endpoints
- Change behavior
- Add configuration
- Implement features

## Testing Locally

### With Mock Gateway

Service can run standalone with mocked lease:

```powershell
# Just run the service
uvicorn app.main:app --reload --port 8003

# Create task (uses mock lease)
curl -X POST http://localhost:8003/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "process_supplier_inbox"}'
```

### With Real Gateway

```powershell
# Start gateway first (Chandan's service)
cd services/gateway
uvicorn app.main:app --port 8000

# Then start agent
cd services/agent
uvicorn app.main:app --port 8003
```

## Debugging

### Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG
```

### Check Ollama

```powershell
# Test connection
curl http://localhost:11434/api/tags

# Test model
ollama run qwen2.5:7b "What is 2+2?"
```

### Trace Requests

Use `--log-level debug` to see all HTTP calls:

```powershell
uvicorn app.main:app --reload --log-level debug
```

## Integration Points

Your service (`agent`) calls:
- **Gateway** for tool execution and lease
- **Ollama** for LLM inference

Your service is called by:
- **Web UI** for task creation/status
- **E2E tests** for scenarios

Coordinate with:
- **Chandan** (gateway) for tool contracts
- **Pavan** (contracts) for schema changes
- **Kirti** (ERP) for test data
- **Yogesh** (UI) for API changes

## Day-by-Day Plan

### Day 1 ✅
- [x] Project structure
- [x] Ollama client
- [x] Tool definitions
- [x] Basic FastAPI app

### Day 2 (Current)
- [ ] Database models & migrations
- [ ] State machine
- [ ] Task creation
- [ ] Model evaluation

### Day 3
- [ ] Replanning logic
- [ ] Approval handling
- [ ] Memory
- [ ] Events

### Day 4
- [ ] Integration testing
- [ ] Error handling
- [ ] Replay mode

### Day 5-7
- [ ] Model selection
- [ ] Golden trace
- [ ] Documentation
- [ ] Demo prep

## Questions?

- **Spec questions**: Check `docs/MASTER_SPEC.md` Section 13
- **Contract questions**: Ask Pavan
- **Gateway integration**: Ask Chandan
- **Test data**: Ask Kirti
- **UI integration**: Ask Yogesh

## Resources

- Master Spec: `docs/MASTER_SPEC.md`
- Your Prompt: `docs/03-Prompt-Harshita.md`
- Development Guide: `services/agent/DEVELOPMENT.md`
- API Docs: http://localhost:8003/docs (when running)
