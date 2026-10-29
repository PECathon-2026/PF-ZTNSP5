from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class MissionStatus(str, Enum):
    CREATED = "CREATED"
    PREFLIGHT = "PREFLIGHT"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    PLANNING = "PLANNING"
    READY_FOR_AUTHORIZATION = "READY_FOR_AUTHORIZATION"
    RUNNING = "RUNNING"
    CHECKING = "CHECKING"
    REPAIRING = "REPAIRING"
    REVIEWING = "REVIEWING"
    VERIFYING = "VERIFYING"
    VERIFIED_AWAITING_APPROVAL = "VERIFIED_AWAITING_APPROVAL"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED_VERIFICATION = "FAILED_VERIFICATION"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class CriterionStatus(str, Enum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    NOT_VERIFIED = "NOT_VERIFIED"
    BLOCKED = "BLOCKED"


class AcceptanceCriterion(BaseModel):
    id: str = Field(default_factory=lambda: f"crit-{uuid4().hex[:8]}")
    mission_id: str
    description: str
    verification_method: str = "test_profile:default"
    status: CriterionStatus = CriterionStatus.PENDING
    evidence_ids: list[str] = Field(default_factory=list)
    criteria_version: int = 1


class MissionBudgets(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)
    max_repair_rounds: int = Field(default=3, ge=0, le=3)
    repair_rounds_used: int = Field(default=0, ge=0)
    max_time_seconds: int = Field(default=600, ge=1, le=3600)
    time_used_seconds: float = Field(default=0.0, ge=0)
    max_tool_calls: int = Field(default=50, ge=1, le=500)
    tool_calls_used: int = Field(default=0, ge=0)
    max_model_turns: int = Field(default=25, ge=1, le=100)
    model_turns_used: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=160000, ge=1, le=1000000)
    input_tokens_used: int = Field(default=0, ge=0)
    output_tokens_used: int = Field(default=0, ge=0)
    max_clarifications: int = Field(default=3, ge=0, le=5)
    clarifications_used: int = Field(default=0, ge=0)


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: f"miss-{uuid4().hex[:8]}")
    repository_id: str
    request_text: str
    status: MissionStatus = MissionStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope_version: int = 1
    active_candidate_id: str | None = None
    budgets: MissionBudgets = Field(default_factory=MissionBudgets)
    unresolved_issues: list[str] = Field(default_factory=list)
    cancel_requested: bool = False
    failure_reason: str | None = None


class CreateMissionRequest(BaseModel):
    repository_id: str
    request_text: str
    criteria: list[str] = Field(default_factory=list)


class ClarificationAnswerRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)
    question_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=4000)

