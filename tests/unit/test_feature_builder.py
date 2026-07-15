"""Unit tests for vera.features.builder.FeatureBuilder."""

from __future__ import annotations

import pytest

from vera.features.builder import FeatureBuilder
from vera.features.feature_set import (
    BusinessHealthFeatures,
    CampaignHistoryFeatures,
    CategoryFeatures,
    ConversationSummaryFeatures,
    CustomerRelationshipFeatures,
    FeatureSet,
    IdentityFeatures,
    MerchantProfileFeatures,
    OfferFeatures,
    PerformanceFeatures,
    TemporalFeatures,
    TriggerFeatures,
)

_IDENTITY = IdentityFeatures(
    merchant_id="m_001",
    category_slug="dentists",
    name="Dr. Meera",
    city=None,
    locality=None,
    place_id=None,
    verified=None,
    languages=(),
    owner_first_name=None,
    established_year=None,
)
_PROFILE = MerchantProfileFeatures(
    subscription_status="active",
    plan=None,
    days_remaining=None,
    days_since_expiry=None,
    is_subscription_active=True,
    renewal_due_soon=False,
)
_PERFORMANCE = PerformanceFeatures(
    window_days=30,
    views=None,
    calls=None,
    directions=None,
    ctr=None,
    leads=None,
    views_delta_pct=None,
    calls_delta_pct=None,
    ctr_delta_pct=None,
)
_OFFERS = OfferFeatures(
    offers=(), offer_count=0, active_offer_count=0, has_live_offer=False, inventory_health="empty"
)
_CAMPAIGN = CampaignHistoryFeatures(
    last_campaign_title=None,
    last_campaign_started_at=None,
    days_since_last_campaign=None,
    campaign_count=0,
    campaign_fatigue=0,
)
_HEALTH = BusinessHealthFeatures(
    signals=(),
    ctr_vs_peer_delta=None,
    rating_delta=None,
    review_velocity=None,
    review_trend=None,
    review_themes=(),
    merchant_growth_trend="unknown",
)
_CONVERSATION = ConversationSummaryFeatures(
    turns=(),
    turn_count=0,
    last_from=None,
    last_engagement=None,
    last_message_at=None,
    days_since_last_touch=None,
    days_since_last_reply=None,
    conversation_recency="none",
)
_CUSTOMER_REL = CustomerRelationshipFeatures(
    total_unique_ytd=None,
    lapsed_count=None,
    retention_pct=None,
    high_risk_adult_count=None,
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
_TRIGGER = TriggerFeatures(
    id="trg_001",
    scope="merchant",
    kind="research_digest",
    source="external",
    urgency=1,
    suppression_key="sup",
    expires_at=None,
    days_until_expiry=None,
    is_expired=False,
    festival_window=False,
    payload={},
)
_CATEGORY = CategoryFeatures(
    slug="dentists",
    display_name=None,
    voice_tone="peer_clinical",
    vocab_allowed=(),
    vocab_taboo=(),
    salutation_examples=(),
    peer_avg_rating=None,
    peer_avg_ctr=None,
    peer_avg_reviews=None,
    offer_catalog=(),
    digest=(),
    digest_count=0,
    seasonal_beats=(),
    trend_signals=(),
)
_TEMPORAL = TemporalFeatures(
    extracted_at="2026-04-26T12:00:00+00:00", season=(), weekend=False, business_open_now=None
)


def _fully_populated_builder() -> FeatureBuilder:
    return (
        FeatureBuilder()
        .with_identity(_IDENTITY)
        .with_merchant_profile(_PROFILE)
        .with_performance(_PERFORMANCE)
        .with_offers(_OFFERS)
        .with_campaign_history(_CAMPAIGN)
        .with_business_health(_HEALTH)
        .with_conversation(_CONVERSATION)
        .with_customer_relationship(_CUSTOMER_REL)
        .with_trigger(_TRIGGER)
        .with_category(_CATEGORY)
        .with_temporal(_TEMPORAL)
    )


def test_build_succeeds_with_all_sections_set() -> None:
    result = _fully_populated_builder().build()

    assert isinstance(result, FeatureSet)
    assert result.identity is _IDENTITY
    assert result.trigger is _TRIGGER


def test_with_methods_return_self_for_fluent_chaining() -> None:
    builder = FeatureBuilder()
    assert builder.with_identity(_IDENTITY) is builder


@pytest.mark.parametrize(
    "skip",
    [
        "with_identity",
        "with_merchant_profile",
        "with_performance",
        "with_offers",
        "with_campaign_history",
        "with_business_health",
        "with_conversation",
        "with_customer_relationship",
        "with_trigger",
        "with_category",
        "with_temporal",
    ],
)
def test_build_raises_when_any_single_section_missing(skip: str) -> None:
    calls = {
        "with_identity": _IDENTITY,
        "with_merchant_profile": _PROFILE,
        "with_performance": _PERFORMANCE,
        "with_offers": _OFFERS,
        "with_campaign_history": _CAMPAIGN,
        "with_business_health": _HEALTH,
        "with_conversation": _CONVERSATION,
        "with_customer_relationship": _CUSTOMER_REL,
        "with_trigger": _TRIGGER,
        "with_category": _CATEGORY,
        "with_temporal": _TEMPORAL,
    }
    builder = FeatureBuilder()
    for name, value in calls.items():
        if name == skip:
            continue
        getattr(builder, name)(value)

    with pytest.raises(ValueError, match="missing required section"):
        builder.build()


def test_build_raises_when_nothing_set() -> None:
    with pytest.raises(ValueError, match="missing required section"):
        FeatureBuilder().build()
