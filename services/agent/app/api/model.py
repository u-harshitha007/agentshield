"""Model management endpoints."""
from fastapi import APIRouter
import structlog

from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger()


@router.get("/model")
async def get_model_info():
    """Get current model configuration and mode."""
    return {
        "model": settings.ollama_model,
        "host": settings.ollama_host,
        "mode": settings.agent_mode,
        "temperature": settings.ollama_temperature,
        "num_ctx": settings.ollama_num_ctx,
        "replay_trace_path": settings.replay_trace_path if settings.agent_mode == "L3" else None,
    }


@router.post("/model")
async def set_model_mode(mode: str):
    """
    Set agent mode (requires admin role in production).
    
    Modes:
    - L0: Live Ollama
    - L3: Replay recorded trace
    """
    if mode not in ["L0", "L3"]:
        return {"error": "Invalid mode, must be L0 or L3"}
    
    # In production, this would update settings and emit event
    # For now, just log
    logger.info("agent.mode.change_requested", old_mode=settings.agent_mode, new_mode=mode)
    
    return {
        "message": f"Mode change to {mode} requested (not persisted in this prototype)",
        "current_mode": settings.agent_mode,
        "requested_mode": mode,
    }
