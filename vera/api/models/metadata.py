"""vera.api.models.metadata — GET /v1/metadata response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetadataResponse(BaseModel):
    """Bot identity response. See challenge-testing-brief.md §2.5."""

    team_name: str
    team_members: list[str] = Field(default_factory=list)
    model: str
    approach: str
    contact_email: str = ""
    version: str
    submitted_at: str | None = None
