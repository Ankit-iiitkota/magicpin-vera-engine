"""
vera.contexts.composed_message — ComposedMessage schema.

Mirrors challenge-brief.md §5. The output contract of `compose()`,
regardless of which trigger kind or category produced it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ComposedMessage(BaseModel):
    """The result of composing category + merchant + trigger (+ customer)."""

    body: str
    cta: Literal["binary", "open_ended", "none"]
    send_as: Literal["vera", "merchant_on_behalf"]
    suppression_key: str
    rationale: str
