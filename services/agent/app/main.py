"""AgentShield Agent Runtime - Main FastAPI application."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, model, tasks
from app.core.config import settings
from app.core.llm import OllamaClient

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info(
        "agent.startup",
        service=settings.service_name,
        port=settings.service_port,
        ollama_host=settings.ollama_host,
        ollama_model=settings.ollama_model,
        agent_mode=settings.agent_mode,
    )
    
    # Check Ollama health
    client = OllamaClient()
    ollama_healthy = await client.health_check()
    
    if not ollama_healthy:
        logger.warning(
            "ollama.not_ready",
            message="Ollama not reachable or model not available",
            model=settings.ollama_model,
        )
    else:
        logger.info("ollama.ready", model=settings.ollama_model)
    
    yield
    
    # Shutdown
    logger.info("agent.shutdown")


app = FastAPI(
    title="AgentShield Agent Runtime",
    description="Real AI agent with local Ollama for supply chain automation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(tasks.router, prefix="/v1", tags=["tasks"])
app.include_router(model.router, prefix="/v1", tags=["model"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "agentshield-agent",
        "version": "0.1.0",
        "status": "running",
        "mode": settings.agent_mode,
    }
