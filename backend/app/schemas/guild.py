"""Strict model proposals. IDs, permissions and mission status remain controller-owned."""

from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator
from app.agents.tool_contracts import ToolArguments

CheckProfile = Literal["python_pytest", "python_syntax"]


class PlannedCriterion(ToolArguments):
    description: str = Field(min_length=1, max_length=2000)
    check_profile: CheckProfile = "python_pytest"


class PlannedTask(ToolArguments):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=6000)
    dependencies: list[str] = Field(default_factory=list, max_length=8)


class GuildPlan(ToolArguments):
    summary: str = Field(min_length=1, max_length=2000)
    criteria: list[PlannedCriterion] = Field(min_length=1, max_length=20)
    tasks: list[PlannedTask] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_graph(self):
        keys = {task.key for task in self.tasks}
        if len(keys) != len(self.tasks):
            raise ValueError("Task keys must be unique")
        if len({c.description for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criteria descriptions must be unique")
        pending = {task.key: set(task.dependencies) for task in self.tasks}
        if any(not dependencies <= keys for dependencies in pending.values()):
            raise ValueError("Unknown task dependency")
        done = set()
        while pending:
            ready = {key for key, deps in pending.items() if deps <= done}
            if not ready:
                raise ValueError("Task dependencies must be acyclic")
            done.update(ready)
            pending = {key: deps for key, deps in pending.items() if key not in ready}
        return self


class ReviewFinding(ToolArguments):
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "BLOCKING"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=3000)
    observed_behavior: str = Field(min_length=1, max_length=2000)
    expected_behavior: str = Field(min_length=1, max_length=2000)
    file_path: str | None = Field(default=None, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class ReviewReport(ToolArguments):
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=20)
    resolved_finding_ids: list[str] = Field(default_factory=list, max_length=50)


class AuthorizeGuildRequest(ToolArguments):
    scope_version: int = Field(ge=1)
    auto_repair: bool | None = None


class RepairPlan(GuildPlan):
    finding_ids: list[str] = Field(min_length=1, max_length=50)


class ClarificationProposal(ToolArguments):
    question: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)


class Clarification(BaseModel):
    id: str = Field(default_factory=lambda: f"question-{uuid4().hex[:16]}")
    mission_id: str
    question: str
    reason: str
    phase: Literal["plan", "repair"]
    candidate_id: str
    candidate_fingerprint: str
    scope_version: int
    status: Literal["OPEN", "ANSWERED"] = "OPEN"
    answer: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: datetime | None = None
