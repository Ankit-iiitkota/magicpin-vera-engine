"""
Signal detector unit tests.

Each primitive signal gets a fires/does-not-fire pair; composites get a
test proving they fire only when ALL/ANY of their constituent signals
are present. Also covers: severity ordering, determinism, and that
SignalDetector only ever touches FeatureSet (never raw context types).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.conftest import (
    extract_features,
    make_category,
    make_customer,
    make_merchant,
    make_trigger,
)
from vera.signals import SignalDetector


def detect(**kwargs):
    return SignalDetector().detect(extract_features(**kwargs))


def test_no_signals_fire_for_a_healthy_baseline_merchant() -> None:
    merchant = make_merchant(
        performance={"views_delta_pct": 0.0, "calls_delta_pct": 0.0},
        offers=[{"title": "Cleaning @ 299", "status": "active", "started": "2026-04-20"}],
        conversation_history=[{"ts": "2026-04-27T10:00:00Z", "from": "merchant", "body": "ok"}],
    )
    trigger = make_trigger(kind="perf_spike", expires_at="2026-06-01T00:00:00Z")
    # 2026-04-27 is a Monday, unlike the shared NOW fixture (Sunday) — this
    # test is specifically about NOTHING firing, so it must avoid the
    # (correctly-firing) WeekendOpportunity signal too.
    ss = detect(merchant=merchant, trigger=trigger, now=datetime(2026, 4, 27, 12, 0, tzinfo=UTC))

    assert ss.is_empty
    assert ss.top is None


def test_revenue_drop_fires_on_severe_calls_dip() -> None:
    fired = detect(merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.50}}))
    not_fired = detect(merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.05}}))

    assert fired.has("RevenueDrop")
    assert fired.get("RevenueDrop").severity == 5
    assert not not_fired.has("RevenueDrop")


def test_search_spike_fires_on_view_surge() -> None:
    fired = detect(merchant=make_merchant(performance={"delta_7d": {"views_pct": 0.30}}))
    not_fired = detect(merchant=make_merchant(performance={"delta_7d": {"views_pct": 0.05}}))

    assert fired.has("SearchSpike")
    assert not not_fired.has("SearchSpike")


def test_offer_expiry_fires_when_offers_exist_but_none_active() -> None:
    fired = detect(merchant=make_merchant(offers=[{"title": "Old", "status": "expired"}]))
    not_fired_empty = detect(merchant=make_merchant(offers=[]))
    not_fired_active = detect(
        merchant=make_merchant(offers=[{"title": "Live", "status": "active"}])
    )

    assert fired.has("OfferExpiry")
    assert not not_fired_empty.has("OfferExpiry")  # empty -> InventoryRisk, not OfferExpiry
    assert not not_fired_active.has("OfferExpiry")


def test_festival_window_mirrors_trigger_features() -> None:
    fired = detect(trigger=make_trigger(kind="festival_upcoming", payload={"days_until": 3}))
    not_fired = detect(trigger=make_trigger(kind="festival_upcoming", payload={"days_until": 188}))

    assert fired.has("FestivalWindow")
    assert not not_fired.has("FestivalWindow")


def test_listing_incomplete_fires_on_unverified_or_missing_fields() -> None:
    unverified = detect(merchant=make_merchant(identity={"name": "X", "verified": False}))
    missing_city = detect(
        merchant=make_merchant(identity={"name": "X", "verified": True, "locality": "Y"})
    )
    complete = detect(
        merchant=make_merchant(
            identity={"name": "X", "verified": True, "city": "Delhi", "locality": "Y"}
        )
    )

    assert unverified.has("ListingIncomplete")
    assert missing_city.has("ListingIncomplete")
    assert not complete.has("ListingIncomplete")


def test_campaign_fatigue_fires_at_threshold() -> None:
    history = [
        {"ts": f"2026-04-{d:02d}T10:00:00Z", "from": "vera", "body": "nudge"} for d in (10, 15, 20)
    ]
    fired = detect(merchant=make_merchant(conversation_history=history))
    not_fired = detect(merchant=make_merchant(conversation_history=history[:2]))

    assert fired.has("CampaignFatigue")
    assert not not_fired.has("CampaignFatigue")


def test_customer_recall_fires_for_lapsed_customer_only() -> None:
    lapsed = make_customer(state="lapsed_soft")
    active = make_customer(state="active")

    assert detect(customer=lapsed).has("CustomerRecall")
    assert not detect(customer=active).has("CustomerRecall")
    assert not detect(customer=None).has("CustomerRecall")


def test_dormant_merchant_fires_after_threshold_days() -> None:
    dormant = detect(
        merchant=make_merchant(
            conversation_history=[{"ts": "2026-03-01T10:00:00Z", "from": "vera", "body": "x"}]
        )
    )
    active = detect(
        merchant=make_merchant(
            conversation_history=[{"ts": "2026-04-25T10:00:00Z", "from": "vera", "body": "x"}]
        )
    )

    assert dormant.has("DormantMerchant")
    assert not active.has("DormantMerchant")


def test_weekend_opportunity_matches_temporal_weekend() -> None:
    # NOW (2026-04-26) is a Sunday.
    assert detect().has("WeekendOpportunity")


def test_review_opportunity_fires_on_positive_trend() -> None:
    positive = detect(
        merchant=make_merchant(
            review_themes=[{"theme": "service", "sentiment": "pos", "occurrences_30d": 5}]
        )
    )
    negative = detect(
        merchant=make_merchant(
            review_themes=[{"theme": "wait", "sentiment": "neg", "occurrences_30d": 5}]
        )
    )

    assert positive.has("ReviewOpportunity")
    assert not negative.has("ReviewOpportunity")


def test_inventory_risk_fires_only_when_no_offers_at_all() -> None:
    assert detect(merchant=make_merchant(offers=[])).has("InventoryRisk")
    assert not detect(merchant=make_merchant(offers=[{"title": "X", "status": "expired"}])).has(
        "InventoryRisk"
    )


def test_local_demand_fires_on_strong_trend_signal() -> None:
    hot = detect(category=make_category(trend_signals=[{"query": "aligners", "delta_yoy": 0.62}]))
    cold = detect(category=make_category(trend_signals=[{"query": "aligners", "delta_yoy": 0.05}]))

    assert hot.has("LocalDemand")
    assert not cold.has("LocalDemand")


def test_research_insight_fires_when_digest_present() -> None:
    present = detect(
        category=make_category(
            digest=[{"id": "d1", "kind": "research", "title": "T", "source": "S"}]
        )
    )
    absent = detect(category=make_category(digest=[]))

    assert present.has("ResearchInsight")
    assert not absent.has("ResearchInsight")


def test_weather_opportunity_matches_weather_trigger_kind() -> None:
    fired = detect(trigger=make_trigger(kind="weather_heatwave", expires_at="2026-06-01T00:00:00Z"))
    not_fired = detect(trigger=make_trigger(kind="perf_spike", expires_at="2026-06-01T00:00:00Z"))
    expired = detect(
        trigger=make_trigger(kind="weather_heatwave", expires_at="2026-01-01T00:00:00Z")
    )

    assert fired.has("WeatherOpportunity")
    assert not not_fired.has("WeatherOpportunity")
    assert not expired.has("WeatherOpportunity")


def test_competition_opportunity_matches_competitor_trigger() -> None:
    fired = detect(
        trigger=make_trigger(kind="competitor_opened", expires_at="2026-06-01T00:00:00Z")
    )
    not_fired = detect(
        trigger=make_trigger(kind="research_digest", expires_at="2026-06-01T00:00:00Z")
    )

    assert fired.has("CompetitionOpportunity")
    assert not not_fired.has("CompetitionOpportunity")


# ── Composite signals ─────────────────────────────────────────────────────


def test_urgent_winback_requires_both_constituents() -> None:
    both = detect(
        merchant=make_merchant(
            conversation_history=[{"ts": "2026-03-01T10:00:00Z", "from": "vera", "body": "x"}]
        ),
        customer=make_customer(state="lapsed_hard"),
    )
    only_dormant = detect(
        merchant=make_merchant(
            conversation_history=[{"ts": "2026-03-01T10:00:00Z", "from": "vera", "body": "x"}]
        )
    )

    assert both.has("DormantMerchant")
    assert both.has("CustomerRecall")
    assert both.has("UrgentWinback")
    assert both.get("UrgentWinback").is_composite is True
    assert not only_dormant.has("UrgentWinback")


def test_growth_momentum_requires_both_constituents() -> None:
    both = detect(
        merchant=make_merchant(
            performance={"delta_7d": {"views_pct": 0.30}},
            review_themes=[{"theme": "x", "sentiment": "pos", "occurrences_30d": 3}],
        )
    )
    only_one = detect(merchant=make_merchant(performance={"delta_7d": {"views_pct": 0.30}}))

    assert both.has("GrowthMomentum")
    assert not only_one.has("GrowthMomentum")


def test_stale_and_fatigued_requires_all_and_any() -> None:
    history = [
        {"ts": f"2026-04-{d:02d}T10:00:00Z", "from": "vera", "body": "nudge"} for d in (10, 15, 20)
    ]
    with_stale = detect(
        merchant=make_merchant(
            conversation_history=history, offers=[{"title": "Old", "status": "expired"}]
        )
    )
    with_empty = detect(merchant=make_merchant(conversation_history=history, offers=[]))
    fatigue_only_healthy_offers = detect(
        merchant=make_merchant(
            conversation_history=history, offers=[{"title": "Live", "status": "active"}]
        )
    )

    assert with_stale.has("StaleAndFatigued")
    assert with_empty.has("StaleAndFatigued")
    assert not fatigue_only_healthy_offers.has("StaleAndFatigued")


# ── Cross-cutting behaviour ───────────────────────────────────────────────


def test_signals_are_ordered_most_severe_first() -> None:
    ss = detect(
        merchant=make_merchant(
            conversation_history=[{"ts": "2026-03-01T10:00:00Z", "from": "vera", "body": "x"}]
        ),
        customer=make_customer(state="lapsed_hard"),
    )
    severities = [s.severity for s in ss.signals]
    assert severities == sorted(severities, reverse=True)


def test_detection_is_deterministic() -> None:
    kwargs = {"merchant": make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})}
    first = detect(**kwargs)
    second = detect(**kwargs)
    assert first == second


def test_detect_requires_features() -> None:
    with pytest.raises(TypeError):
        SignalDetector().detect(None)  # type: ignore[arg-type]


def test_from_config_loads_real_yaml_definitions() -> None:
    detector = SignalDetector.from_config("vera/signals/yaml/signal_definitions.yaml")
    ss = detector.detect(
        extract_features(merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}}))
    )
    signal = ss.get("RevenueDrop")
    assert signal is not None
    assert "revenue-adjacent" in signal.rationale_hint or "Calls or views" in signal.rationale_hint
