from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class CandidateState(str, Enum):
    MUTABLE = "MUTABLE"
    FROZEN = "FROZEN"
    SUPERSEDED = "SUPERSEDED"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class Candidate(BaseModel):
    id: str = Field(default_factory=lambda: f"cand-{uuid4().hex[:8]}")
    mission_id: str
    parent_candidate_id: str | None = None
    workspace_snapshot_id: str
    content_fingerprint: str
    changed_files: list[str] = Field(default_factory=list)
    criteria_version: int = 1
    state: CandidateState = CandidateState.MUTABLE
    ui_badge: str = "PROPOSED"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

