"""Tests for agent executor."""
import pytest

from app.core.agent import AgentExecutor


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent can be initialized."""
    executor = AgentExecutor()
    assert executor.llm is not None
    assert executor.tools is not None
    assert executor.replanner is not None


# TODO: Add tests with mocked LLM and gateway
# - test_execute_task_success
# - test_execute_task_with_replan
# - test_execute_task_max_steps
# - test_execute_task_budget_exhausted
