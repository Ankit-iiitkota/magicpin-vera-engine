"""
vera.api.models.reply — POST /v1/reply request/response schemas.

See challenge-testing-brief.md §2.3. Wired to a live endpoint in Phase 5;
Phase 1 only defines the schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str | None = None
    customer_id: str | None = None
    from_role: Literal["merchant", "customer"]
    message: str
    received_at: str
    turn_number: int


class ReplySendResponse(BaseModel):
    action: Literal["send"] = "send"
    body: str
    cta: Literal["binary", "open_ended", "none"]
    rationale: str


class ReplyWaitResponse(BaseModel):
    action: Literal["wait"] = "wait"
    wait_seconds: int
    rationale: str


class ReplyEndResponse(BaseModel):
    action: Literal["end"] = "end"
    rationale: str
