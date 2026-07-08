"""
vera.features.merchant_features — MerchantContext -> per-section features.

Split into small, independently testable pure functions (one per
FeatureSet section) rather than one monolithic extractor, so each is
trivial to unit-test with a hand-built MerchantContext.

`now` is passed in explicitly everywhere instead of being read from the
system clock in here — see FeatureExtractor.extract() for why
(determinism: same inputs + same `now` => byte-identical FeatureSet).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.features.feature_set import (
    CampaignHistoryFeatures,
    ConversationSummaryFeatures,
    ConversationTurnRecord,
    IdentityFeatures,
    MerchantProfileFeatures,
    OfferFeatures,
    OfferRecord,
    PerformanceFeatures,
)
from vera.utils.time_utils import parse_iso8601_safe

if TYPE_CHECKING:
    from datetime import datetime

    from vera.contexts.merchant import MerchantContext

__all__ = [
    "extract_campaign_history",
    "extract_conversation_summary",
    "extract_identity",
    "extract_merchant_profile",
    "extract_offers",
    "extract_performance",
]

#: A subscription with this many days (or fewer) left counts as "due soon".
#: Matches the dataset's own signal convention, e.g. "renewal_due_soon:12d".
RENEWAL_DUE_SOON_DAYS = 14

#: A conversation touched within this many days still counts "active".
ACTIVE_TOUCH_DAYS = 2


def extract_identity(merchant: MerchantContext) -> IdentityFeatures:
    identity = merchant.identity
    return IdentityFeatures(
        merchant_id=merchant.merchant_id,
        category_slug=merchant.category_slug,
        name=identity.name,
        city=identity.city,
        locality=identity.locality,
        place_id=identity.place_id,
        verified=identity.verified,
        languages=tuple(identity.languages),
        owner_first_name=identity.owner_first_name,
        established_year=identity.established_year,
    )


def extract_merchant_profile(merchant: MerchantContext) -> MerchantProfileFeatures:
    sub = merchant.subscription
    renewal_due_soon = (
        sub.days_remaining is not None and 0 <= sub.days_remaining <= RENEWAL_DUE_SOON_DAYS
    )
    return MerchantProfileFeatures(
        subscription_status=sub.status,
        plan=sub.plan,
        days_remaining=sub.days_remaining,
        days_since_expiry=sub.days_since_expiry,
        is_subscription_active=sub.status == "active",
        renewal_due_soon=renewal_due_soon,
    )


def extract_performance(merchant: MerchantContext) -> PerformanceFeatures:
    perf = merchant.performance
    delta = perf.delta_7d
    return PerformanceFeatures(
        window_days=perf.window_days,
        views=perf.views,
        calls=perf.calls,
        directions=perf.directions,
        ctr=perf.ctr,
        leads=perf.leads,
        views_delta_pct=delta.views_pct if delta else None,
        calls_delta_pct=delta.calls_pct if delta else None,
        ctr_delta_pct=delta.ctr_pct if delta else None,
    )


def extract_offers(merchant: MerchantContext) -> OfferFeatures:
    offers = tuple(
        OfferRecord(id=o.id, title=o.title, status=o.status, started=o.started, ended=o.ended)
        for o in merchant.offers
    )
    active_count = sum(1 for o in offers if o.status == "active")

    if not offers:
        inventory_health = "empty"
    elif active_count > 0:
        inventory_health = "healthy"
    else:
        inventory_health = "stale"

    return OfferFeatures(
        offers=offers,
        offer_count=len(offers),
        active_offer_count=active_count,
        has_live_offer=active_count > 0,
        inventory_health=inventory_health,
    )


def extract_campaign_history(merchant: MerchantContext, now: datetime) -> CampaignHistoryFeatures:
    """
    "Campaign" == a deployed offer (see CampaignHistoryFeatures docstring).
    campaign_fatigue counts consecutive, most-recent-first Vera-authored
    conversation turns with no merchant reply after them yet — how many
    unanswered nudges in a row right now.
    """
    dated = [
        (offer, dt)
        for offer in merchant.offers
        if (dt := parse_iso8601_safe(offer.started)) is not None
    ]
    if dated:
        latest_offer, latest_dt = max(dated, key=lambda pair: pair[1])
        days_since_last_campaign = (now - latest_dt).days
        last_campaign_title = latest_offer.title
        last_campaign_started_at = latest_offer.started
    else:
        days_since_last_campaign = None
        last_campaign_title = None
        last_campaign_started_at = None

    campaign_fatigue = 0
    for turn in reversed(merchant.conversation_history):
        if turn.from_ != "vera":
            break
        campaign_fatigue += 1

    return CampaignHistoryFeatures(
        last_campaign_title=last_campaign_title,
        last_campaign_started_at=last_campaign_started_at,
        days_since_last_campaign=days_since_last_campaign,
        campaign_count=len(merchant.offers),
        campaign_fatigue=campaign_fatigue,
    )


def extract_conversation_summary(
    merchant: MerchantContext, now: datetime, dormancy_threshold_days: int
) -> ConversationSummaryFeatures:
    turns = tuple(
        ConversationTurnRecord(ts=t.ts, from_role=t.from_, body=t.body, engagement=t.engagement)
        for t in merchant.conversation_history
    )

    if not turns:
        return ConversationSummaryFeatures(
            turns=(),
            turn_count=0,
            last_from=None,
            last_engagement=None,
            last_message_at=None,
            days_since_last_touch=None,
            days_since_last_reply=None,
            conversation_recency="none",
        )

    last = turns[-1]
    last_dt = parse_iso8601_safe(last.ts)
    days_since_last_touch = (now - last_dt).days if last_dt is not None else None

    last_reply = next((t for t in reversed(turns) if t.from_role == "merchant"), None)
    if last_reply is not None:
        reply_dt = parse_iso8601_safe(last_reply.ts)
        days_since_last_reply = (now - reply_dt).days if reply_dt is not None else None
    else:
        days_since_last_reply = None

    if days_since_last_touch is None:
        recency = "none"
    elif days_since_last_touch < ACTIVE_TOUCH_DAYS:
        recency = "active"
    elif days_since_last_touch < dormancy_threshold_days:
        recency = "recent"
    else:
        recency = "dormant"

    return ConversationSummaryFeatures(
        turns=turns,
        turn_count=len(turns),
        last_from=last.from_role,
        last_engagement=last.engagement,
        last_message_at=last.ts,
        days_since_last_touch=days_since_last_touch,
        days_since_last_reply=days_since_last_reply,
        conversation_recency=recency,
    )
