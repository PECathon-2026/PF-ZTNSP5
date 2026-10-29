from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class MissionEvent(BaseModel):
    sequence: int  # Monotonically increasing sequence per mission
    mission_id: str
    event_type: str
    source: str
    task_id: str | None = None
    candidate_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    display_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

