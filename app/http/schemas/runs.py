from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRecordResponse(BaseModel):
    ok: bool = True
    record: dict[str, Any] | None = None


class RunStepsResponse(BaseModel):
    ok: bool = True
    steps: list[dict[str, Any]] = Field(default_factory=list)


class RunEventsResponse(BaseModel):
    ok: bool = True
    events: list[dict[str, Any]] = Field(default_factory=list)
