"""
Goal inferrer unit tests.

Builds SignalSet instances by hand (Signal(kind=..., ...)) rather than
running the full extractor+detector pipeline, since GoalInferenceEngine
only ever touches SignalSet — this keeps the tests focused on rule
priority/tie-breaking logic in isolation.
"""

from __future__ import annotations

import pytest

from vera.goals import DEFAULT_GOAL, GoalInferenceEngine, GoalRules
from vera.goals.goal_rules import GoalRule
from vera.signals.signal_set import Signal, SignalSet


def _signal(kind: str, severity: int = 3, is_composite: bool = False) -> Signal:
    return Signal(
        kind=kind, severity=severity, is_composite=is_composite, rationale_hint=kind, evidence={}
    )


def _signal_set(*signals: Signal) -> SignalSet:
    return SignalSet(signals=tuple(sorted(signals, key=lambda s: -s.severity)))


@pytest.fixture
def engine() -> GoalInferenceEngine:
    return GoalInferenceEngine()


def test_empty_signal_set_falls_back_to_default_goal(engine: GoalInferenceEngine) -> None:
    gc = engine.infer(_signal_set())

    assert gc.primary_goal == DEFAULT_GOAL
    assert gc.secondary_goals == ()
    assert gc.supporting_signals == ()
    assert "default" in gc.rationale.lower() or "No signal" in gc.rationale


def test_single_signal_maps_to_its_goal(engine: GoalInferenceEngine) -> None:
    gc = engine.infer(_signal_set(_signal("ReviewOpportunity")))

    assert gc.primary_goal == "COLLECT_REVIEWS"
    assert gc.supporting_signals == ("ReviewOpportunity",)


@pytest.mark.parametrize(
    ("kind", "expected_goal"),
    [
        ("RevenueDrop", "RECOVER_REVENUE"),
        ("CustomerRecall", "WIN_BACK_CUSTOMERS"),
        ("UrgentWinback", "WIN_BACK_CUSTOMERS"),
        ("CampaignFatigue", "REDUCE_CHURN"),
        ("DormantMerchant", "REDUCE_CHURN"),
        ("StaleAndFatigued", "REDUCE_CHURN"),
        ("OfferExpiry", "PROMOTE_OFFERS"),
        ("InventoryRisk", "PROMOTE_OFFERS"),
        ("ListingIncomplete", "IMPROVE_LISTINGS"),
        ("ReviewOpportunity", "COLLECT_REVIEWS"),
        ("WeekendOpportunity", "INCREASE_SALES"),
        ("FestivalWindow", "INCREASE_SALES"),
        ("LocalDemand", "INCREASE_SALES"),
        ("WeatherOpportunity", "INCREASE_SALES"),
        ("GrowthMomentum", "INCREASE_SALES"),
        ("SearchSpike", "INCREASE_VISIBILITY"),
        ("ResearchInsight", "INCREASE_VISIBILITY"),
        ("CompetitionOpportunity", "INCREASE_VISIBILITY"),
    ],
)
def test_every_signal_kind_maps_to_the_expected_goal(
    engine: GoalInferenceEngine, kind: str, expected_goal: str
) -> None:
    assert engine.infer(_signal_set(_signal(kind))).primary_goal == expected_goal


def test_high_severity_signal_can_outrank_a_higher_priority_rule() -> None:
    """Scoring, not first-match: a severity-5 signal on a low-priority
    goal (INCREASE_VISIBILITY, priority 8) can outscore a severity-1
    signal on a high-priority goal (RECOVER_REVENUE, priority 1) — the
    whole point of "score all applicable goals, pick the highest"."""
    engine = GoalInferenceEngine()
    high_sev_low_priority = _signal("SearchSpike", severity=5)
    low_sev_high_priority = _signal("RevenueDrop", severity=1)

    gc = engine.infer(_signal_set(high_sev_low_priority, low_sev_high_priority))

    assert gc.primary_goal == "INCREASE_VISIBILITY"
    assert "RECOVER_REVENUE" in gc.secondary_goals


def test_priority_breaks_ties_when_severity_scores_are_equal() -> None:
    """With equal severity and equal signal count, the higher-priority
    (lower priority number) rule still wins — priority remains a real,
    deterministic tie-breaker, just not an absolute override."""
    engine = GoalInferenceEngine()
    reduce_churn_signal = _signal("CampaignFatigue", severity=3)
    visibility_signal = _signal("SearchSpike", severity=3)

    gc = engine.infer(_signal_set(reduce_churn_signal, visibility_signal))

    assert gc.primary_goal == "REDUCE_CHURN"


def test_multiple_corroborating_signals_can_outrank_a_single_stronger_priority() -> None:
    """Two independent signals backing REDUCE_CHURN (priority 3) can
    outscore a single equally-weak RECOVER_REVENUE (priority 1) signal —
    breadth of evidence matters, not just which rule appears first."""
    engine = GoalInferenceEngine()
    ss = _signal_set(
        _signal("RevenueDrop", severity=1),
        _signal("CampaignFatigue", severity=1),
        _signal("DormantMerchant", severity=1),
    )

    gc = engine.infer(ss)

    assert gc.primary_goal == "REDUCE_CHURN"
    assert "RECOVER_REVENUE" in gc.secondary_goals


def test_secondary_goals_are_deduplicated_and_exclude_primary() -> None:
    engine = GoalInferenceEngine()
    # A strong RevenueDrop keeps RECOVER_REVENUE primary; two
    # REDUCE_CHURN-mapped signals must still not produce a duplicate
    # secondary-goal entry.
    ss = _signal_set(
        _signal("RevenueDrop", severity=5),
        _signal("CampaignFatigue", severity=1),
        _signal("DormantMerchant", severity=1),
    )
    gc = engine.infer(ss)

    assert gc.primary_goal == "RECOVER_REVENUE"
    assert gc.secondary_goals.count("REDUCE_CHURN") == 1
    assert "RECOVER_REVENUE" not in gc.secondary_goals


def test_inference_is_deterministic(engine: GoalInferenceEngine) -> None:
    ss = _signal_set(_signal("RevenueDrop"), _signal("ListingIncomplete"))
    assert engine.infer(ss) == engine.infer(ss)


def test_infer_requires_signal_set(engine: GoalInferenceEngine) -> None:
    with pytest.raises(TypeError):
        engine.infer(None)  # type: ignore[arg-type]


def test_from_config_loads_real_yaml() -> None:
    engine = GoalInferenceEngine.from_config()
    gc = engine.infer(_signal_set(_signal("RevenueDrop")))
    assert gc.primary_goal == "RECOVER_REVENUE"


# ── GoalRules validation ─────────────────────────────────────────────────


def test_goal_rules_default_construction_uses_fallback() -> None:
    rules = GoalRules()
    assert len(rules.rules) == 8
    assert rules.rules[0].priority <= rules.rules[-1].priority  # sorted ascending


def test_goal_rules_rejects_unknown_goal() -> None:
    with pytest.raises(ValueError, match="unknown goal"):
        GoalRules([{"goal": "NOT_A_REAL_GOAL", "priority": 1, "requires_any": ["X"]}])


def test_goal_rules_rejects_missing_priority() -> None:
    with pytest.raises(ValueError, match="priority"):
        GoalRules([{"goal": "RECOVER_REVENUE", "requires_any": ["RevenueDrop"]}])


def test_goal_rules_rejects_empty_requires_any() -> None:
    with pytest.raises(ValueError, match="requires_any"):
        GoalRules([{"goal": "RECOVER_REVENUE", "priority": 1, "requires_any": []}])


def test_goal_rule_is_a_plain_dataclass() -> None:
    rule = GoalRule(goal="RECOVER_REVENUE", priority=1, requires_any=("RevenueDrop",))
    assert rule.goal == "RECOVER_REVENUE"
