"""Task management endpoints."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.agent import AgentExecutor
from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger()

# In-memory task store (TODO: replace with DB)
tasks_store = {}


class CreateTaskRequest(BaseModel):
    """Request to create a new task."""
    goal: str
    context: dict | None = None
    template: str = "AP_INBOX_V1"


class TaskResponse(BaseModel):
    """Task response."""
    task_id: str
    status: str
    goal: str
    created_at: str
    lease_id: str | None = None
    current_step: int = 0


async def execute_task_background(task_id: str, goal: str, lease_token: str):
    """Execute task in background."""
    executor = AgentExecutor()
    
    try:
        result = await executor.execute_task(task_id, goal, lease_token)
        
        # Update task store
        if task_id in tasks_store:
            tasks_store[task_id].update({
                "status": result["status"],
                "current_step": result.get("current_step", 0),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            })
        
        logger.info("task.background.completed", task_id=task_id, status=result["status"])
        
    except Exception as e:
        logger.error("task.background.failed", task_id=task_id, error=str(e))
        if task_id in tasks_store:
            tasks_store[task_id].update({
                "status": "FAILED",
                "failure_reason": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest, background_tasks: BackgroundTasks):
    """
    Create a new agent task.
    
    This will:
    1. Create task record
    2. Request capability lease from gateway
    3. Start agent execution in background
    """
    task_id = str(uuid4())
    
    logger.info("task.create.requested", task_id=task_id, goal=request.goal)
    
    # Request lease from gateway
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            lease_response = await client.post(
                f"{settings.gateway_url}/v1/tasks",
                json={
                    "task_id": task_id,
                    "template": request.template,
                    "context": request.context or {},
                },
                headers={"Authorization": f"Bearer {settings.agent_service_token}"},
            )
            
            if lease_response.status_code != 200:
                raise HTTPException(
                    status_code=lease_response.status_code,
                    detail=f"Failed to obtain lease: {lease_response.text}",
                )
            
            lease_data = lease_response.json()
            
    except httpx.HTTPError as e:
        logger.error("lease.request_failed", error=str(e))
        # For demo, create a mock lease
        lease_data = {
            "task_id": task_id,
            "lease_id": f"lease-{task_id}",
            "lease_token": f"mock-lease-token-{task_id}",
            "expires_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.warning("using_mock_lease", message="Gateway not available, using mock lease")
    
    # Create task record
    task = {
        "task_id": task_id,
        "goal": request.goal,
        "status": "RECEIVED",
        "lease_id": lease_data.get("lease_id"),
        "lease_token": lease_data.get("lease_token"),
        "current_step": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context": request.context or {},
    }
    
    tasks_store[task_id] = task
    
    # Start execution in background
    background_tasks.add_task(
        execute_task_background,
        task_id,
        request.goal,
        lease_data.get("lease_token"),
    )
    
    logger.info("task.created", task_id=task_id, lease_id=lease_data.get("lease_id"))
    
    return TaskResponse(
        task_id=task_id,
        status="RECEIVED",
        goal=request.goal,
        created_at=task["created_at"],
        lease_id=lease_data.get("lease_id"),
    )


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status and summary."""
    task = tasks_store.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task["task_id"],
        "goal": task["goal"],
        "status": task["status"],
        "current_step": task.get("current_step", 0),
        "created_at": task["created_at"],
        "completed_at": task.get("completed_at"),
        "lease_id": task.get("lease_id"),
    }


@router.get("/tasks/{task_id}/trace")
async def get_task_trace(task_id: str):
    """Get detailed execution trace for a task."""
    task = tasks_store.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = task.get("result", {})
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "observations": result.get("observations", []),
        "memory": result.get("memory", {}),
        "stats": {
            "llm_calls": result.get("llm_calls_count", 0),
            "tool_calls": result.get("tool_calls_count", 0),
            "replans": result.get("replans_count", 0),
        },
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    task = tasks_store.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] in ["COMPLETED", "FAILED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail=f"Task already {task['status']}")
    
    task["status"] = "CANCELLED"
    task["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    logger.info("task.cancelled", task_id=task_id)
    
    return {"task_id": task_id, "status": "CANCELLED"}
