from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CapabilityResponse(BaseModel):
    ok: bool = True
    capabilities: dict[str, Any] = Field(default_factory=dict)


class ConfigResponse(BaseModel):
    ok: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ConfigPatchRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)
