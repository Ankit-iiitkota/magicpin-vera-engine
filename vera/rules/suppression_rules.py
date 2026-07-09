"""
vera.rules.suppression_rules — computing the final suppression_key.

TriggerContext always carries its own suppression_key (it's a required
field — challenge-testing-brief.md §3.4), and the dataset's own
triggers already fold the customer_id in for customer-scoped kinds
(e.g. "recall:c_001_priya_for_m001:6mo"). This is mostly pass-through;
the one real rule is a safety net — if a customer-facing send's
suppression_key somehow doesn't already mention that customer, append
it, so a customer-scoped dedup key can never collide with the same
trigger's merchant-facing send.
"""

from __future__ import annotations

__all__ = ["resolve_suppression_key"]


def resolve_suppression_key(trigger_suppression_key: str, customer_id: str | None) -> str:
    if customer_id and customer_id not in trigger_suppression_key:
        return f"{trigger_suppression_key}:{customer_id}"
    return trigger_suppression_key
