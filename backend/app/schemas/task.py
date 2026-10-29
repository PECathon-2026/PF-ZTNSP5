from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:8]}")
    mission_id: str
    title: str
    description: str
    owner_agent: str  # "SHOGUN" | "SAMURAI" | "SENTINEL" | "SHADOW_COUNCIL"
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempt: int = 1
    candidate_id: str | None = None
    completion_condition: str | None = None
    result_summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

