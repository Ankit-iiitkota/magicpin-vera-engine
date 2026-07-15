"""
Feature extractor unit tests.

Covers the full extraction pipeline against real dataset fixtures,
determinism, immutability, and every edge case Phase 3 calls out
explicitly: missing payloads, null values, partial merchant, partial
trigger, empty offers, empty history.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vera.contexts import CategoryContext, CustomerContext, MerchantContext, TriggerContext
from vera.features import FeatureExtractor
from vera.features.cross_features import _month_in_range

DATASET_DIR = Path(__file__).resolve().parents[2] / "magicpin-ai-challenge" / "dataset"
NOW = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


# ── Minimal fixture factories — only the Pydantic-required fields, so
#    edge-case tests can build "the smallest legal context" and override
#    just what they care about. ────────────────────────────────────────────


def make_category(**overrides) -> CategoryContext:
    data = {"slug": "dentists", "voice": {"tone": "peer_clinical"}}
    data.update(overrides)
    return CategoryContext.model_validate(data)


def make_merchant(**overrides) -> MerchantContext:
    data = {
        "merchant_id": "m_001",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera's Dental Clinic"},
        "subscription": {"status": "active"},
        "performance": {},
    }
    data.update(overrides)
    return MerchantContext.model_validate(data)


def make_trigger(**overrides) -> TriggerContext:
    data = {
        "id": "trg_001",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "suppression_key": "research:dentists:2026-W17",
        "expires_at": "2026-05-03T00:00:00Z",
    }
    data.update(overrides)
    return TriggerContext.model_validate(data)


def make_customer(**overrides) -> CustomerContext:
    data = {
        "customer_id": "c_001",
        "merchant_id": "m_001",
        "identity": {"name": "Priya"},
        "relationship": {},
        "state": "active",
        "preferences": {},
        "consent": {},
    }
    data.update(overrides)
    return CustomerContext.model_validate(data)


@pytest.fixture
def extractor() -> FeatureExtractor:
    return FeatureExtractor()


# ── Full pipeline against the real dataset ──────────────────────────────────


def test_full_extraction_against_real_dataset(extractor: FeatureExtractor) -> None:
    category = CategoryContext.model_validate(
        json.loads((DATASET_DIR / "categories" / "dentists.json").read_text(encoding="utf-8"))
    )
    merchants = json.loads((DATASET_DIR / "merchants_seed.json").read_text(encoding="utf-8"))
    merchant = MerchantContext.model_validate(merchants["merchants"][0])  # Dr. Meera
    triggers = json.loads((DATASET_DIR / "triggers_seed.json").read_text(encoding="utf-8"))
    trigger = TriggerContext.model_validate(triggers["triggers"][0])  # research digest, m_001
    customers = json.loads((DATASET_DIR / "customers_seed.json").read_text(encoding="utf-8"))
    customer = CustomerContext.model_validate(customers["customers"][0])  # Priya

    fs = extractor.extract(category, merchant, trigger, customer=customer, now=NOW)

    assert fs.identity.merchant_id == "m_001_drmeera_dentist_delhi"
    assert fs.identity.category_slug == "dentists"
    assert fs.offers.offer_count == 2
    assert fs.offers.active_offer_count == 1
    assert fs.offers.has_live_offer is True
    assert fs.offers.inventory_health == "healthy"
    assert fs.campaign_history.days_since_last_campaign == 56
    assert fs.business_health.ctr_vs_peer_delta == pytest.approx(0.021 - 0.030)
    assert fs.business_health.rating_delta is None
    assert fs.business_health.review_velocity == 8  # 3 (wait_time) + 5 (doctor_manner)
    assert fs.business_health.review_trend == "mixed"  # 1 pos, 1 neg
    assert fs.conversation.turn_count == 2
    assert fs.conversation.days_since_last_reply == 2
    assert fs.customer_relationship.has_customer_context is True
    assert fs.customer_relationship.customer_state == "lapsed_soft"
    assert fs.trigger.kind == "research_digest"
    assert fs.trigger.is_expired is False
    assert fs.category.digest_count == 5
    assert len(fs.category.offer_catalog) == 8
    assert fs.temporal.weekend is True  # 2026-04-26 is a Sunday
    assert fs.temporal.business_open_now is None


def test_extraction_is_deterministic(extractor: FeatureExtractor) -> None:
    category, merchant, trigger, customer = (
        make_category(),
        make_merchant(),
        make_trigger(),
        make_customer(),
    )

    first = extractor.extract(category, merchant, trigger, customer=customer, now=NOW)
    second = extractor.extract(category, merchant, trigger, customer=customer, now=NOW)

    # Structural equality proves determinism. FeatureSet is deliberately
    # not hashable: trigger.payload is a free-form, kind-specific mapping
    # (its shape isn't modelled per-kind until Phase 8's strategies), and
    # a dict-backed field can never be made hashable without deep-freezing
    # arbitrarily nested structures — not worth it for a field this system
    # only ever compares by equality, never uses as a dict/set key.
    assert first == second


def test_no_customer_context_is_reflected_consistently(extractor: FeatureExtractor) -> None:
    fs = extractor.extract(make_category(), make_merchant(), make_trigger(), customer=None, now=NOW)

    cr = fs.customer_relationship
    assert cr.has_customer_context is False
    assert cr.customer_id is None
    assert cr.customer_state is None
    assert cr.customer_visits_total is None
    assert cr.customer_loyalty_score is None


def test_feature_set_and_nested_records_are_immutable(extractor: FeatureExtractor) -> None:
    fs = extractor.extract(make_category(), make_merchant(), make_trigger(), now=NOW)

    with pytest.raises(Exception, match="frozen|assign"):
        fs.identity.merchant_id = "hacked"  # type: ignore[misc]

    merchant_with_offer = make_merchant(offers=[{"title": "Cleaning @ 299", "status": "active"}])
    fs2 = extractor.extract(make_category(), merchant_with_offer, make_trigger(), now=NOW)
    with pytest.raises(Exception, match="frozen|assign"):
        fs2.offers.offers[0].title = "hacked"  # type: ignore[misc]


def test_required_contexts_cannot_be_none(extractor: FeatureExtractor) -> None:
    category, merchant, trigger = make_category(), make_merchant(), make_trigger()
    with pytest.raises(TypeError):
        extractor.extract(None, merchant, trigger)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        extractor.extract(category, None, trigger)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        extractor.extract(category, merchant, None)  # type: ignore[arg-type]


# ── Explicit Phase 3 edge cases ──────────────────────────────────────────────


def test_edge_case_missing_optional_payloads(extractor: FeatureExtractor) -> None:
    """category.peer_stats and merchant.customer_aggregate both absent."""
    category = make_category()  # peer_stats defaults to None
    merchant = make_merchant()  # customer_aggregate defaults to None
    trigger = make_trigger()

    fs = extractor.extract(category, merchant, trigger, now=NOW)

    assert fs.category.peer_avg_ctr is None
    assert fs.category.peer_avg_rating is None
    assert fs.business_health.ctr_vs_peer_delta is None
    assert fs.customer_relationship.total_unique_ytd is None
    assert fs.customer_relationship.lapsed_count is None


def test_edge_case_null_values_scattered_through_merchant(extractor: FeatureExtractor) -> None:
    merchant = make_merchant(
        identity={"name": "Bare Bones Clinic", "verified": None, "languages": []},
        subscription={"status": "active", "days_remaining": None},
        performance={"ctr": None, "delta_7d": None},
    )
    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.identity.verified is None
    assert fs.identity.languages == ()
    assert fs.merchant_profile.days_remaining is None
    assert fs.merchant_profile.renewal_due_soon is False
    assert fs.performance.ctr is None
    assert fs.performance.ctr_delta_pct is None
    assert fs.business_health.merchant_growth_trend == "unknown"


def test_edge_case_partial_merchant_only_required_fields(extractor: FeatureExtractor) -> None:
    """A MerchantContext with nothing but the Pydantic-required fields set."""
    merchant = make_merchant()

    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.offers.offer_count == 0
    assert fs.conversation.turn_count == 0
    assert fs.business_health.review_velocity is None
    assert fs.business_health.signals == ()
    assert fs.campaign_history.campaign_count == 0


def test_edge_case_partial_trigger_only_required_fields(extractor: FeatureExtractor) -> None:
    """A TriggerContext with merchant_id/customer_id/payload all absent-ish."""
    trigger = make_trigger(merchant_id=None, customer_id=None, payload={}, urgency=1)

    fs = extractor.extract(make_category(), make_merchant(), trigger, now=NOW)

    assert fs.trigger.payload == {}
    assert fs.trigger.festival_window is False
    assert fs.trigger.urgency == 1
    assert fs.trigger.days_until_expiry is not None  # expires_at is always required


def test_edge_case_empty_offers(extractor: FeatureExtractor) -> None:
    merchant = make_merchant(offers=[])

    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.offers.offer_count == 0
    assert fs.offers.active_offer_count == 0
    assert fs.offers.has_live_offer is False
    assert fs.offers.inventory_health == "empty"
    assert fs.campaign_history.days_since_last_campaign is None
    assert fs.campaign_history.last_campaign_title is None


def test_edge_case_empty_conversation_history(extractor: FeatureExtractor) -> None:
    merchant = make_merchant(conversation_history=[])

    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.conversation.turn_count == 0
    assert fs.conversation.last_from is None
    assert fs.conversation.days_since_last_touch is None
    assert fs.conversation.days_since_last_reply is None
    assert fs.conversation.conversation_recency == "none"
    assert fs.campaign_history.campaign_fatigue == 0


def test_offers_with_no_started_date_do_not_count_as_a_campaign(
    extractor: FeatureExtractor,
) -> None:
    merchant = make_merchant(
        offers=[{"title": "Mystery offer", "status": "active"}]  # no `started`
    )
    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.offers.offer_count == 1  # still counts as an offer...
    assert fs.campaign_history.days_since_last_campaign is None  # ...but not a dated campaign


def test_campaign_fatigue_counts_consecutive_unanswered_vera_touches(
    extractor: FeatureExtractor,
) -> None:
    merchant = make_merchant(
        conversation_history=[
            {"ts": "2026-04-01T10:00:00Z", "from": "merchant", "body": "ok"},
            {"ts": "2026-04-10T10:00:00Z", "from": "vera", "body": "nudge 1"},
            {"ts": "2026-04-15T10:00:00Z", "from": "vera", "body": "nudge 2"},
            {"ts": "2026-04-20T10:00:00Z", "from": "vera", "body": "nudge 3"},
        ]
    )
    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.campaign_history.campaign_fatigue == 3


def test_conversation_recency_buckets(extractor: FeatureExtractor) -> None:
    active = make_merchant(
        conversation_history=[{"ts": "2026-04-25T10:00:00Z", "from": "vera", "body": "x"}]
    )
    recent = make_merchant(
        conversation_history=[{"ts": "2026-04-20T10:00:00Z", "from": "vera", "body": "x"}]
    )
    dormant = make_merchant(
        conversation_history=[{"ts": "2026-03-01T10:00:00Z", "from": "vera", "body": "x"}]
    )

    assert (
        extractor.extract(
            make_category(), active, make_trigger(), now=NOW
        ).conversation.conversation_recency
        == "active"
    )
    assert (
        extractor.extract(
            make_category(), recent, make_trigger(), now=NOW
        ).conversation.conversation_recency
        == "recent"
    )
    assert (
        extractor.extract(
            make_category(), dormant, make_trigger(), now=NOW
        ).conversation.conversation_recency
        == "dormant"
    )


@pytest.mark.parametrize(
    ("ctr_delta", "expected"),
    [(0.25, "growing"), (-0.20, "declining"), (0.01, "stable"), (None, "unknown")],
)
def test_merchant_growth_trend_thresholds(extractor: FeatureExtractor, ctr_delta, expected) -> None:
    delta_7d = {"ctr_pct": ctr_delta} if ctr_delta is not None else None
    merchant = make_merchant(performance={"delta_7d": delta_7d} if delta_7d else {})
    fs = extractor.extract(make_category(), merchant, make_trigger(), now=NOW)

    assert fs.business_health.merchant_growth_trend == expected


def test_festival_window_true_within_threshold_false_beyond_it(extractor: FeatureExtractor) -> None:
    near = make_trigger(kind="festival_upcoming", payload={"days_until": 5})
    far = make_trigger(kind="festival_upcoming", payload={"days_until": 188})
    unrelated = make_trigger(kind="perf_dip", payload={"days_until": 1})

    assert (
        extractor.extract(make_category(), make_merchant(), near, now=NOW).trigger.festival_window
        is True
    )
    assert (
        extractor.extract(make_category(), make_merchant(), far, now=NOW).trigger.festival_window
        is False
    )
    assert (
        extractor.extract(
            make_category(), make_merchant(), unrelated, now=NOW
        ).trigger.festival_window
        is False
    )


def test_trigger_is_expired_flag(extractor: FeatureExtractor) -> None:
    expired = make_trigger(expires_at="2026-01-01T00:00:00Z")
    fs = extractor.extract(make_category(), make_merchant(), expired, now=NOW)

    assert fs.trigger.is_expired is True
    assert fs.trigger.days_until_expiry < 0


def test_season_matches_wraparound_range() -> None:
    # "Nov-Feb" spans the year boundary; December and January both match.
    assert _month_in_range(12, "Nov-Feb") is True
    assert _month_in_range(1, "Nov-Feb") is True
    assert _month_in_range(6, "Nov-Feb") is False
    assert _month_in_range(1, "Jan") is True
    assert _month_in_range(2, "Jan") is False
    assert _month_in_range(4, "bogus-range") is False  # malformed input never crashes


def test_business_open_now_and_rating_delta_are_always_none(extractor: FeatureExtractor) -> None:
    """Documented, deliberate: neither field exists in the context schema."""
    fs = extractor.extract(make_category(), make_merchant(), make_trigger(), now=NOW)

    assert fs.temporal.business_open_now is None
    assert fs.business_health.rating_delta is None


def test_customer_loyalty_score_uses_visits_and_state(extractor: FeatureExtractor) -> None:
    loyal = make_customer(relationship={"visits_total": 20, "lifetime_value": 5000}, state="active")
    churned = make_customer(
        relationship={"visits_total": 20, "lifetime_value": 5000}, state="churned"
    )

    loyal_fs = extractor.extract(
        make_category(), make_merchant(), make_trigger(), customer=loyal, now=NOW
    )
    churned_fs = extractor.extract(
        make_category(), make_merchant(), make_trigger(), customer=churned, now=NOW
    )

    assert (
        loyal_fs.customer_relationship.customer_loyalty_score
        > churned_fs.customer_relationship.customer_loyalty_score
    )
    assert churned_fs.customer_relationship.customer_loyalty_score == 0.0


def test_from_config_loads_real_settings_yaml() -> None:
    extractor = FeatureExtractor.from_config("config/settings.yaml")
    fs = extractor.extract(
        make_category(),
        make_merchant(
            conversation_history=[{"ts": "2026-04-10T10:00:00Z", "from": "vera", "body": "x"}]
        ),
        make_trigger(),
        now=NOW,
    )
    # dormancy_threshold_days: 14 in config/settings.yaml — 16 days since
    # touch must land in "dormant", proving the YAML value was actually used.
    assert fs.conversation.conversation_recency == "dormant"


def test_from_config_falls_back_to_defaults_for_missing_file() -> None:
    extractor = FeatureExtractor.from_config("config/does_not_exist.yaml")
    fs = extractor.extract(make_category(), make_merchant(), make_trigger(), now=NOW)
    assert fs is not None  # no crash — load_yaml() returns {} for a missing file
