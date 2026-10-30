"""Event emission for audit and observability."""
from datetime import datetime, timezone

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class EventEmitter:
    """Emit events to gateway for audit trail."""
    
    def __init__(self):
        self.gateway_url = settings.gateway_url
        self.service_token = settings.agent_service_token
    
    async def emit(self, event_type: str, payload: dict):
        """
        Emit event to gateway.
        
        Event types:
        - agent.task.created
        - agent.task.completed
        - agent.task.failed
        - agent.llm.call
        - agent.tool.called
        - agent.replanned
        - agent.step.completed
        """
        event = {
            "event_id": f"evt-{datetime.now(timezone.utc).timestamp()}",
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "agent",
            "payload": payload,
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.gateway_url}/v1/events",
                    json=event,
                    headers={"Authorization": f"Bearer {self.service_token}"},
                )
            
            logger.debug("event.emitted", event_type=event_type)
            
        except Exception as e:
            logger.warning("event.emit_failed", event_type=event_type, error=str(e))
