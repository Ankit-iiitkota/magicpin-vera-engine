"""vera.api.models.health — GET /v1/healthz response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthzResponse(BaseModel):
    """Liveness probe response. See challenge-testing-brief.md §2.4."""

    status: str = Field(default="ok")
    uptime_seconds: int
    contexts_loaded: dict[str, int]
