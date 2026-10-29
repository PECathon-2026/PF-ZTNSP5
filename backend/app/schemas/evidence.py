from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field


class EvidenceKind(str, Enum):
    TEST = "TEST"
    BUILD = "BUILD"
    LINT = "LINT"
    STATIC_SCAN = "STATIC_SCAN"
    DIFF = "DIFF"
    REVIEW_FINDING = "REVIEW_FINDING"
    BASELINE = "BASELINE"
    MUTATION = "MUTATION"


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: f"ev-{uuid4().hex[:8]}")
    mission_id: str
    candidate_id: str
    criterion_id: str | None = None
    kind: EvidenceKind
    source: str
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    duration_ms: int = 0
    stdout_artifact_id: str | None = None
    stderr_artifact_id: str | None = None
    fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

