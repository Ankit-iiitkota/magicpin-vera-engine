"""
vera.features.customer_features — customer relationship features.

Combines two independent sources into one section:
  - MerchantContext.customer_aggregate — always available, describes
    the merchant's whole customer roster in aggregate.
  - CustomerContext — optional, only present for customer-facing
    composition (challenge-brief.md §4.4); describes one specific
    customer.

has_customer_context discriminates the two: every field prefixed
`customer_*` is None unless a CustomerContext was actually supplied.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.features.feature_set import CustomerRelationshipFeatures
from vera.utils.time_utils import parse_iso8601_safe

if TYPE_CHECKING:
    from datetime import datetime

    from vera.contexts.customer import CustomerContext, Relationship
    from vera.contexts.merchant import MerchantContext

__all__ = ["extract_customer_relationship"]

#: Deterministic, documented weighting — not a prediction. Loyalty score
#: = visits_total * state_weight + a small bounded lifetime-value bonus.
_STATE_WEIGHT = {
    "new": 0.2,
    "active": 1.0,
    "lapsed_soft": 0.5,
    "lapsed_hard": 0.2,
    "churned": 0.0,
}
_LTV_BONUS_DIVISOR = 1000
_LTV_BONUS_CAP = 5


def extract_customer_relationship(
    merchant: MerchantContext, customer: CustomerContext | None, now: datetime
) -> CustomerRelationshipFeatures:
    agg = merchant.customer_aggregate
    total_unique_ytd = agg.total_unique_ytd if agg else None
    lapsed_count = None
    retention_pct = None
    high_risk_adult_count = None
    if agg is not None:
        lapsed_count = (
            agg.lapsed_180d_plus if agg.lapsed_180d_plus is not None else agg.lapsed_90d_plus
        )
        retention_pct = (
            agg.retention_6mo_pct if agg.retention_6mo_pct is not None else agg.retention_3mo_pct
        )
        high_risk_adult_count = agg.high_risk_adult_count

    if customer is None:
        return CustomerRelationshipFeatures(
            total_unique_ytd=total_unique_ytd,
            lapsed_count=lapsed_count,
            retention_pct=retention_pct,
            high_risk_adult_count=high_risk_adult_count,
            has_customer_context=False,
            customer_id=None,
            customer_name=None,
            customer_state=None,
            customer_language_pref=None,
            customer_visits_total=None,
            customer_lifetime_value=None,
            customer_last_visit=None,
            customer_days_since_last_visit=None,
            customer_preferred_slots=None,
            customer_loyalty_score=None,
        )

    rel = customer.relationship
    last_visit_dt = parse_iso8601_safe(rel.last_visit)
    days_since_last_visit = (now - last_visit_dt).days if last_visit_dt is not None else None

    return CustomerRelationshipFeatures(
        total_unique_ytd=total_unique_ytd,
        lapsed_count=lapsed_count,
        retention_pct=retention_pct,
        high_risk_adult_count=high_risk_adult_count,
        has_customer_context=True,
        customer_id=customer.customer_id,
        customer_name=customer.identity.name,
        customer_state=customer.state,
        customer_language_pref=customer.identity.language_pref,
        customer_visits_total=rel.visits_total,
        customer_lifetime_value=rel.lifetime_value,
        customer_last_visit=rel.last_visit,
        customer_days_since_last_visit=days_since_last_visit,
        customer_preferred_slots=customer.preferences.preferred_slots,
        customer_loyalty_score=_compute_loyalty_score(rel, customer.state),
    )


def _compute_loyalty_score(rel: Relationship, state: str) -> float | None:
    if rel.visits_total is None:
        return None
    state_weight = _STATE_WEIGHT.get(state, 0.5)
    ltv_bonus = min((rel.lifetime_value or 0) / _LTV_BONUS_DIVISOR, _LTV_BONUS_CAP)
    # state_weight multiplies the *whole* volume (visits + ltv bonus), not
    # just the visit count — a churned customer's historical spend doesn't
    # make them currently loyal, so state_weight=0 must zero the score
    # entirely, not just the visits term.
    return round((rel.visits_total + ltv_bonus) * state_weight, 2)
