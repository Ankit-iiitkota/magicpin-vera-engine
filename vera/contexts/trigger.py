"""
vera.contexts.trigger — TriggerContext schema.

Mirrors challenge-brief.md §4.3 and challenge-testing-brief.md §3.4.
The event that prompts a message right now. Every composed message
must have exactly one.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TriggerContext(BaseModel):
    """The event driving a single send."""

    model_config = ConfigDict(extra="allow")

    id: str
    scope: Literal["merchant", "customer"]
    kind: str
    source: Literal["external", "internal"]
    merchant_id: str | None = None
    customer_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    urgency: int = Field(default=1, ge=1, le=5)
    suppression_key: str
    expires_at: str
