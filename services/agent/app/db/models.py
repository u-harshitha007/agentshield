"""Database models for agent service."""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TaskStatus(str, Enum):
    """Task status enum."""
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REPLANNING = "REPLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task(Base):
    """Agent task model."""
    __tablename__ = "tasks"
    __table_args__ = {"schema": "agent"}
    
    task_id = Column(String, primary_key=True)
    goal = Column(String, nullable=False)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.RECEIVED)
    
    # Lease info
    lease_id = Column(String)
    lease_token = Column(Text)
    lease_expires_at = Column(DateTime(timezone=True))
    
    # Execution tracking
    current_step = Column(Integer, default=0)
    tool_calls_count = Column(Integer, default=0)
    llm_calls_count = Column(Integer, default=0)
    replans_count = Column(Integer, default=0)
    denials_count = Column(Integer, default=0)
    
    # Context
    context = Column(JSON)
    memory = Column(JSON)
    
    # Result
    result_summary = Column(Text)
    failure_reason = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status.value if self.status else None,
            "lease_id": self.lease_id,
            "current_step": self.current_step,
            "tool_calls_count": self.tool_calls_count,
            "llm_calls_count": self.llm_calls_count,
            "replans_count": self.replans_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TraceSpan(Base):
    """Execution trace span."""
    __tablename__ = "trace_spans"
    __table_args__ = {"schema": "agent"}
    
    span_id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False, index=True)
    parent_span_id = Column(String)
    
    span_type = Column(String, nullable=False)  # plan, step, llm_call, tool_call
    name = Column(String)
    
    # LLM specific
    llm_call_id = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    
    # Tool specific
    tool_name = Column(String)
    decision_id = Column(String)
    decision = Column(String)
    reason_code = Column(String)
    
    # Data
    input_data = Column(JSON)
    output_data = Column(JSON)
    
    # Timing
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True))
    latency_ms = Column(Integer)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "span_id": self.span_id,
            "task_id": self.task_id,
            "parent_span_id": self.parent_span_id,
            "span_type": self.span_type,
            "name": self.name,
            "tool_name": self.tool_name,
            "decision_id": self.decision_id,
            "decision": self.decision,
            "latency_ms": self.latency_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }
