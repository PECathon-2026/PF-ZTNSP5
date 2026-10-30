"""Explicit recovery decisions bound to a freshly inspected checkpoint."""

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.mission import MissionLimits


class CheckpointDecision(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    checkpoint_token: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContinueMissionRequest(CheckpointDecision):
    accept_partial_edits: bool = False


class BudgetExtensionRequest(CheckpointDecision):
    limits: MissionLimits
