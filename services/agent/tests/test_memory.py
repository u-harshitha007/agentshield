"""Tests for task memory management."""
import pytest

from app.core.memory import TaskMemory


def test_memory_initialization():
    """Test memory can be initialized."""
    memory = TaskMemory("task-123")
    assert memory.task_id == "task-123"
    assert len(memory.facts) == 0


def test_store_erp_fact():
    """Test storing ERP data."""
    memory = TaskMemory("task-123")
    
    memory.store_fact("purchase_order", {"po": "4500017"}, source="erp")
    
    assert memory.get_fact("purchase_order") == {"po": "4500017"}
    assert not memory.is_external("purchase_order")


def test_store_external_fact():
    """Test storing external data."""
    memory = TaskMemory("task-123")
    
    memory.store_fact("inbox_message", {"from": "attacker@evil.com"}, source="external")
    
    assert memory.get_fact("inbox_message") == {"from": "attacker@evil.com"}
    assert memory.is_external("inbox_message")


def test_get_all_facts():
    """Test retrieving all facts."""
    memory = TaskMemory("task-123")
    
    memory.store_fact("po", {"id": "123"}, source="erp")
    memory.store_fact("supplier", {"id": "456"}, source="erp")
    
    all_facts = memory.get_all()
    
    assert len(all_facts) == 2
    assert "po" in all_facts
    assert "supplier" in all_facts


def test_memory_summarize():
    """Test memory summary."""
    memory = TaskMemory("task-123")
    
    memory.store_fact("po", {"id": "123"}, source="erp")
    memory.store_fact("msg", {"text": "..."}, source="external")
    
    summary = memory.summarize()
    
    assert summary["facts_count"] == 2
    assert "msg" in summary["external_refs"]
    assert summary["keys"] == ["po", "msg"]
