"""
vera.api.models.context — POST /v1/context request/response schemas.

See challenge-testing-brief.md §2.1. Wired to a live endpoint in Phase 2
(vera.api.endpoints.context).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

#: The four scopes the judge harness pushes over HTTP. Kept as a plain
#: `str` on the request model (not `Literal[...]`) so an invalid scope
#: fails inside the endpoint with the spec's documented 400
#: `{"reason": "invalid_scope"}` body, rather than FastAPI's generic 422.
ALLOWED_PUSH_SCOPES = ("category", "merchant", "customer", "trigger")

#: challenge-testing-brief.md §5: "/v1/context payload size cap: 500 KB".
MAX_PAYLOAD_BYTES = 500 * 1024


class ContextPushRequest(BaseModel):
    scope: str
    context_id: str = Field(min_length=1)
    version: int = Field(gt=0)
    payload: dict[str, Any]
    delivered_at: str

    @field_validator("payload")
    @classmethod
    def _payload_within_size_cap(cls, value: dict[str, Any]) -> dict[str, Any]:
        size = len(json.dumps(value).encode("utf-8"))
        if size > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"payload is {size} bytes, exceeds the {MAX_PAYLOAD_BYTES}-byte "
                "(500 KB) cap from challenge-testing-brief.md §5"
            )
        return value


class ContextPushAccepted(BaseModel):
    accepted: Literal[True] = True
    ack_id: str
    stored_at: str


class ContextPushRejected(BaseModel):
    accepted: Literal[False] = False
    reason: str
    current_version: int | None = None
    details: str | None = None
