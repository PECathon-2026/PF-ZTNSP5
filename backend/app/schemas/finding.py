from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKING = "BLOCKING"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ACCEPTED_WITH_RISK = "ACCEPTED_WITH_RISK"
    REJECTED = "REJECTED"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: f"find-{uuid4().hex[:8]}")
    mission_id: str
    source_agent: str
    severity: FindingSeverity
    title: str
    description: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    observed_behavior: str
    expected_behavior: str
    evidence_ids: list[str] = Field(default_factory=list)
    candidate_id: str | None = None
    status: FindingStatus = FindingStatus.OPEN
    resolution_evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

