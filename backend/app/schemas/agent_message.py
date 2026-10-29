from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    TASK_PROPOSAL = "TASK_PROPOSAL"
    TASK_RESULT = "TASK_RESULT"
    FINDING = "FINDING"
    CLARIFICATION = "CLARIFICATION"
    CHECK_REQUEST = "CHECK_REQUEST"
    BLOCKER = "BLOCKER"
    HANDOFF = "HANDOFF"


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: f"msg-{uuid4().hex[:8]}")
    mission_id: str
    sender: str
    recipient: str
    type: MessageType
    task_id: str | None = None
    candidate_id: str | None = None
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

