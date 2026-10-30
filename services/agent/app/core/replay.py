"""Replay mode implementation for deterministic demo playback."""
import json
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger()


class ReplayManager:
    """
    Manages L3 replay mode.
    
    In replay mode:
    - Model outputs are loaded from a recorded trace file
    - Tool calls still go through live gateway (security decisions are live)
    - LLM is bypassed, but all other logic runs normally
    """
    
    def __init__(self):
        self.mode = settings.agent_mode
        self.trace_path = settings.replay_trace_path
        self.replay_data = None
        self.replay_index = 0
        
        if self.mode == "L3":
            self._load_trace()
    
    def _load_trace(self):
        """Load recorded trace for replay."""
        try:
            trace_file = Path(self.trace_path)
            
            if not trace_file.exists():
                logger.warning(
                    "replay.trace_not_found",
                    path=self.trace_path,
                    message="Trace file not found, falling back to L0",
                )
                self.mode = "L0"
                return
            
            with open(trace_file, 'r') as f:
                self.replay_data = json.load(f)
            
            logger.info(
                "replay.trace_loaded",
                path=self.trace_path,
                steps=len(self.replay_data.get("steps", [])),
            )
            
        except Exception as e:
            logger.error("replay.load_failed", error=str(e), path=self.trace_path)
            self.mode = "L0"
    
    def is_replay_mode(self) -> bool:
        """Check if in replay mode."""
        return self.mode == "L3" and self.replay_data is not None
    
    def get_next_action(self) -> dict[str, Any] | None:
        """
        Get next recorded action from trace.
        
        Returns:
            dict with tool, args, reasoning, or None if replay exhausted
        """
        if not self.is_replay_mode():
            return None
        
        steps = self.replay_data.get("steps", [])
        
        if self.replay_index >= len(steps):
            logger.warning("replay.exhausted", index=self.replay_index, total=len(steps))
            return None
        
        action = steps[self.replay_index]
        self.replay_index += 1
        
        logger.info(
            "replay.action_retrieved",
            index=self.replay_index,
            tool=action.get("tool"),
            recorded_at=self.replay_data.get("recorded_at"),
        )
        
        return action
    
    def reset(self):
        """Reset replay index."""
        self.replay_index = 0


def create_replay_trace(steps: list[dict], metadata: dict) -> dict:
    """
    Create a replay trace structure.
    
    Args:
        steps: List of recorded actions with tool, args, reasoning
        metadata: Task metadata (goal, task_id, recorded_at, etc.)
    
    Returns:
        Trace dictionary ready to be saved
    """
    return {
        "version": "1.0",
        "recorded_at": metadata.get("recorded_at"),
        "task_id": metadata.get("task_id"),
        "goal": metadata.get("goal"),
        "steps": steps,
        "metadata": metadata,
    }
