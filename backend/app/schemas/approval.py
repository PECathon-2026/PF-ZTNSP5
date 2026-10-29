from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


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
    candidate_id: str
    candidate_fingerprint: str
    decision: ApprovalDecision


class ApplyPatchRequest(BaseModel):
    candidate_id: str

