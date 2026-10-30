"""Health check endpoint."""
from fastapi import APIRouter
import structlog

from app.core.config import settings
from app.core.llm import OllamaClient

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Checks:
    - Service is running
    - Ollama is reachable
    - Database connection (TODO)
    """
    ollama_client = OllamaClient()
    ollama_healthy = await ollama_client.health_check()
    
    status = "healthy" if ollama_healthy else "degraded"
    
    return {
        "status": status,
        "service": settings.service_name,
        "version": "0.1.0",
        "checks": {
            "ollama": "pass" if ollama_healthy else "fail",
            "database": "skip",  # TODO: implement DB check
        },
        "config": {
            "model": settings.ollama_model,
            "mode": settings.agent_mode,
            "max_steps": settings.max_steps,
        },
    }
