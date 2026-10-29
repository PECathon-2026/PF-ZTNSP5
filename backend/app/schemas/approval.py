from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Approval(BaseModel):
    id: str = Field(default_factory=lambda: f"appr-{uuid4().hex[:8]}")
    mission_id: str
    candidate_id: str
    candidate_fingerprint: str
    intended_action: str = "APPLY_PATCH"
    decision: ApprovalDecision
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    application_result_id: str | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    candidate_id: str = Field(min_length=1)
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: ApprovalDecision


class ApplyPatchRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    candidate_id: str = Field(min_length=1)

