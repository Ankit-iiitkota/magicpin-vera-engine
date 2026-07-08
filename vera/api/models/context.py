"""
vera.api.models.context — POST /v1/context request/response schemas.

See challenge-testing-brief.md §2.1. Wired to a live endpoint in Phase 2;
Phase 1 only defines the schema.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ContextPushRequest(BaseModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str


class ContextPushAccepted(BaseModel):
    accepted: Literal[True] = True
    ack_id: str
    stored_at: str


class ContextPushRejected(BaseModel):
    accepted: Literal[False] = False
    reason: str
    current_version: int | None = None
    details: str | None = None
