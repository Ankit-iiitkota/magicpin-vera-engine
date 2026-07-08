"""
vera.api.models.tick — POST /v1/tick request/response schemas.

See challenge-testing-brief.md §2.2. Wired to a live endpoint in Phase 5;
Phase 1 only defines the schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: str | None = None
    send_as: Literal["vera", "merchant_on_behalf"]
    trigger_id: str
    template_name: str | None = None
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: Literal["binary", "open_ended", "none"]
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[ActionItem] = Field(default_factory=list)
