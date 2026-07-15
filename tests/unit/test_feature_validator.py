"""Unit tests for vera.features.validator.FeatureValidator."""

from __future__ import annotations

import dataclasses
import math

import pytest

from vera.features.feature_set import (
    BusinessHealthFeatures,
    CampaignHistoryFeatures,
    CategoryFeatures,
    ConversationSummaryFeatures,
    ConversationTurnRecord,
    CustomerRelationshipFeatures,
    FeatureSet,
    IdentityFeatures,
    MerchantProfileFeatures,
    OfferFeatures,
    OfferRecord,
    PerformanceFeatures,
    TemporalFeatures,
    TriggerFeatures,
)
from vera.features.validator import FeatureValidationError, FeatureValidator


def _valid_feature_set() -> FeatureSet:
    return FeatureSet(
        identity=IdentityFeatures(
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
        ),
        merchant_profile=MerchantProfileFeatures(
            subscription_status="active",
            plan=None,
            days_remaining=None,
            days_since_expiry=None,
            is_subscription_active=True,
            renewal_due_soon=False,
        ),
        performance=PerformanceFeatures(
            window_days=30,
            views=None,
            calls=None,
            directions=None,
            ctr=0.02,
            leads=None,
            views_delta_pct=None,
            calls_delta_pct=None,
            ctr_delta_pct=None,
        ),
        offers=OfferFeatures(
            offers=(
                OfferRecord(id="o1", title="Cleaning", status="active", started=None, ended=None),
            ),
            offer_count=1,
            active_offer_count=1,
            has_live_offer=True,
            inventory_health="healthy",
        ),
        campaign_history=CampaignHistoryFeatures(
            last_campaign_title=None,
            last_campaign_started_at=None,
            days_since_last_campaign=None,
            campaign_count=1,
            campaign_fatigue=0,
        ),
        business_health=BusinessHealthFeatures(
            signals=(),
            ctr_vs_peer_delta=None,
            rating_delta=None,
            review_velocity=None,
            review_trend=None,
            review_themes=(),
            merchant_growth_trend="unknown",
        ),
        conversation=ConversationSummaryFeatures(
            turns=(
                ConversationTurnRecord(
                    ts="2026-04-24T10:00:00Z", from_role="vera", body="hi", engagement=None
                ),
            ),
            turn_count=1,
            last_from="vera",
            last_engagement=None,
            last_message_at="2026-04-24T10:00:00Z",
            days_since_last_touch=2,
            days_since_last_reply=None,
            conversation_recency="recent",
        ),
        customer_relationship=CustomerRelationshipFeatures(
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
        ),
        trigger=TriggerFeatures(
            id="trg_001",
            scope="merchant",
            kind="research_digest",
            source="external",
            urgency=2,
            suppression_key="sup",
            expires_at=None,
            days_until_expiry=None,
            is_expired=False,
            festival_window=False,
            payload={},
        ),
        category=CategoryFeatures(
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
        ),
        temporal=TemporalFeatures(
            extracted_at="2026-04-26T12:00:00+00:00",
            season=(),
            weekend=False,
            business_open_now=None,
        ),
    )


def test_valid_feature_set_passes() -> None:
    FeatureValidator().validate(_valid_feature_set())  # must not raise


def test_catches_empty_merchant_id() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, identity=dataclasses.replace(fs.identity, merchant_id=""))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("merchant_id" in issue for issue in exc_info.value.issues)


def test_catches_category_slug_mismatch_between_identity_and_category() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, category=dataclasses.replace(fs.category, slug="salons"))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("does not match" in issue for issue in exc_info.value.issues)


def test_catches_nan_ctr() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, performance=dataclasses.replace(fs.performance, ctr=math.nan))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("NaN" in issue for issue in exc_info.value.issues)


def test_catches_negative_ctr() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, performance=dataclasses.replace(fs.performance, ctr=-0.5))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("ctr" in issue for issue in exc_info.value.issues)


@pytest.mark.parametrize("bad_urgency", [0, 6, -1])
def test_catches_urgency_out_of_range(bad_urgency: int) -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, trigger=dataclasses.replace(fs.trigger, urgency=bad_urgency))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("urgency" in issue for issue in exc_info.value.issues)


def test_catches_offer_count_mismatch() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, offers=dataclasses.replace(fs.offers, offer_count=99))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("offer_count" in issue for issue in exc_info.value.issues)


def test_catches_active_offer_count_exceeding_total() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, offers=dataclasses.replace(fs.offers, active_offer_count=99))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("active_offer_count" in issue for issue in exc_info.value.issues)


def test_catches_conversation_turn_count_mismatch() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, conversation=dataclasses.replace(fs.conversation, turn_count=99))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)
    assert any("turn_count" in issue for issue in exc_info.value.issues)


def test_collects_every_issue_not_just_the_first() -> None:
    fs = _valid_feature_set()
    fs = dataclasses.replace(fs, identity=dataclasses.replace(fs.identity, merchant_id=""))
    fs = dataclasses.replace(fs, trigger=dataclasses.replace(fs.trigger, urgency=0))
    fs = dataclasses.replace(fs, offers=dataclasses.replace(fs.offers, offer_count=99))

    with pytest.raises(FeatureValidationError) as exc_info:
        FeatureValidator().validate(fs)

    assert len(exc_info.value.issues) >= 3
