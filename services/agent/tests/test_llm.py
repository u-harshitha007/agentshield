"""Tests for LLM client."""
import pytest

from app.core.llm import OllamaClient


@pytest.mark.asyncio
async def test_ollama_client_initialization():
    """Test Ollama client can be initialized."""
    client = OllamaClient()
    assert client.model
    assert client.host
    assert client.temperature >= 0
    

# TODO: Add more tests with mocked Ollama responses
# - test_chat_with_tools
# - test_chat_with_format_schema
# - test_plan_action
# - test_health_check
