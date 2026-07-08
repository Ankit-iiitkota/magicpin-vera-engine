"""
vera.api.endpoints.healthz — GET /v1/healthz.

Liveness probe polled every 60s by the judge harness (challenge-testing-brief.md
§2.4). Three consecutive non-200 responses disqualify the bot for that test
slot, so this handler must stay independent of any business-logic pipeline.

contexts_loaded is read straight from the store's own counters — no
composition, scoring, or rule evaluation happens here.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from vera.api.deps import get_started_at, get_store
from vera.api.models.health import HealthzResponse
from vera.store.base_store import BaseContextStore

router = APIRouter(tags=["health"])

_SCOPES = ("category", "merchant", "customer", "trigger")


@router.get("/v1/healthz", response_model=HealthzResponse)
async def healthz(
    store: BaseContextStore = Depends(get_store),
    started_at: float = Depends(get_started_at),
) -> HealthzResponse:
    counts = await store.count_all()
    return HealthzResponse(
        status="ok",
        uptime_seconds=int(time.monotonic() - started_at),
        contexts_loaded={scope: counts.get(scope, 0) for scope in _SCOPES},
    )
