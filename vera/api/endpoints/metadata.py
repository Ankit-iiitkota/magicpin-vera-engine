"""
vera.api.endpoints.metadata — GET /v1/metadata.

Bot identity response (challenge-testing-brief.md §2.5). Phase 1 returns
placeholder identity fields sourced from Settings; `team_members`,
`submitted_at` and the approach description are filled in properly once
the submission is finalized in Phase 9.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vera.api.deps import get_app_settings
from vera.api.models.metadata import MetadataResponse
from vera.config import Settings

router = APIRouter(tags=["metadata"])


@router.get("/v1/metadata", response_model=MetadataResponse)
async def metadata(settings: Settings = Depends(get_app_settings)) -> MetadataResponse:
    return MetadataResponse(
        team_name=settings.team_name,
        team_members=[],
        model="deterministic rule/template engine (no LLM at inference time)",
        approach=(
            "4-context composition (category, merchant, trigger, customer) via a "
            "deterministic feature/signal/goal/template pipeline — see engagement-design.md"
        ),
        contact_email=settings.contact_email,
        version=settings.app_version,
        submitted_at=None,
    )
