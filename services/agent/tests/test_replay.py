"""Tests for replay mode."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from app.core.replay import ReplayManager, create_replay_trace


def test_replay_disabled_by_default():
    """Test replay mode is disabled when mode=L0."""
    with patch('app.core.replay.settings') as mock_settings:
        mock_settings.agent_mode = "L0"
        mock_settings.replay_trace_path = "traces/test.json"
        
        replay = ReplayManager()
        
        assert not replay.is_replay_mode()


def test_replay_trace_not_found_falls_back():
    """Test graceful fallback when trace file missing."""
    with patch('app.core.replay.settings') as mock_settings:
        mock_settings.agent_mode = "L3"
        mock_settings.replay_trace_path = "traces/nonexistent.json"
        
        replay = ReplayManager()
        
        # Should fall back to L0
        assert not replay.is_replay_mode()


def test_create_replay_trace():
    """Test replay trace creation."""
    steps = [
        {"tool": "read_inbox", "args": {}, "reasoning": "Start task"},
        {"tool": "get_purchase_order", "args": {"purchase_order": "4500017"}, "reasoning": "Fetch PO"},
    ]
    
    metadata = {
        "task_id": "task-123",
        "goal": "process_supplier_inbox",
        "recorded_at": "2026-10-31T12:00:00Z",
    }
    
    trace = create_replay_trace(steps, metadata)
    
    assert trace["version"] == "1.0"
    assert trace["task_id"] == "task-123"
    assert len(trace["steps"]) == 2
    assert trace["steps"][0]["tool"] == "read_inbox"


def test_get_next_action():
    """Test retrieving actions from replay."""
    # Create temp trace file
    trace_data = {
        "version": "1.0",
        "steps": [
            {"tool": "read_inbox", "args": {}, "reasoning": "Start"},
            {"tool": "complete_task", "args": {"summary": "Done"}, "reasoning": "Finish"},
        ],
    }
    
    trace_path = Path("traces/test_replay.json")
    trace_path.parent.mkdir(exist_ok=True)
    
    with open(trace_path, 'w') as f:
        json.dump(trace_data, f)
    
    try:
        with patch('app.core.replay.settings') as mock_settings:
            mock_settings.agent_mode = "L3"
            mock_settings.replay_trace_path = str(trace_path)
            
            replay = ReplayManager()
            
            assert replay.is_replay_mode()
            
            # Get first action
            action1 = replay.get_next_action()
            assert action1["tool"] == "read_inbox"
            
            # Get second action
            action2 = replay.get_next_action()
            assert action2["tool"] == "complete_task"
            
            # Exhausted
            action3 = replay.get_next_action()
            assert action3 is None
    
    finally:
        # Clean up
        if trace_path.exists():
            trace_path.unlink()


def test_replay_reset():
    """Test resetting replay index."""
    trace_data = {
        "version": "1.0",
        "steps": [
            {"tool": "read_inbox", "args": {}, "reasoning": "Start"},
        ],
    }
    
    trace_path = Path("traces/test_reset.json")
    trace_path.parent.mkdir(exist_ok=True)
    
    with open(trace_path, 'w') as f:
        json.dump(trace_data, f)
    
    try:
        with patch('app.core.replay.settings') as mock_settings:
            mock_settings.agent_mode = "L3"
            mock_settings.replay_trace_path = str(trace_path)
            
            replay = ReplayManager()
            
            # Get action
            action1 = replay.get_next_action()
            assert action1 is not None
            
            # Reset
            replay.reset()
            
            # Can get same action again
            action2 = replay.get_next_action()
            assert action2["tool"] == action1["tool"]
    
    finally:
        if trace_path.exists():
            trace_path.unlink()
