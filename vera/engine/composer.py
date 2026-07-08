"""
vera.engine.composer — the composition entry point.

`compose()` is the function signature defined by challenge-brief.md §5:

    compose(category, merchant, trigger, customer=None) -> ComposedMessage

It will orchestrate the full deterministic pipeline (feature extraction →
signal detection → goal inference → candidate generation → template
ranking → weighted scoring → fallback chain → output validation) across
Phases 2-8. Phase 1 only fixes the signature and return type so the API
layer and submission wrapper have a stable contract to import against.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.contexts.category import CategoryContext
    from vera.contexts.composed_message import ComposedMessage
    from vera.contexts.customer import CustomerContext
    from vera.contexts.merchant import MerchantContext
    from vera.contexts.trigger import TriggerContext


def compose(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None = None,
) -> ComposedMessage:
    """Compose the next outbound message from the four context layers."""
    raise NotImplementedError("Phase 2")
