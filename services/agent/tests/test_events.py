"""Tests for event emission."""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.events import EventEmitter


@pytest.mark.asyncio
async def test_event_emitter_initialization():
    """Test event emitter can be initialized."""
    emitter = EventEmitter()
    assert emitter.gateway_url is not None
    assert emitter.service_token is not None


@pytest.mark.asyncio
async def test_event_emission_success():
    """Test successful event emission."""
    emitter = EventEmitter()
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Should not raise
        await emitter.emit("agent.task.created", {"task_id": "test-123"})


@pytest.mark.asyncio
async def test_event_emission_failure_does_not_crash():
    """Test that event emission failures are gracefully handled."""
    emitter = EventEmitter()
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("Network error"))
        
        # Should not raise, just log warning
        await emitter.emit("agent.task.failed", {"task_id": "test-456"})
