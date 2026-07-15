"""
Candidate generator unit tests.

Runs the real pipeline (FeatureExtractor -> SignalDetector ->
GoalInferenceEngine -> CandidateGenerator) for realistic coverage, plus
isolated tests against hand-built GoalContext for the count/priority/
language rules specifically.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from tests.conftest import extract_features, make_customer, make_merchant
from vera.candidates import COMPULSION_LEVERS, Candidate, CandidateGenerator
from vera.goals import GoalContext
from vera.goals.goal_inferrer import GoalInferenceEngine
from vera.signals.signal_detector import SignalDetector


def run_pipeline(**kwargs):
    features = extract_features(**kwargs)
    signals = SignalDetector().detect(features)
    goal_context = GoalInferenceEngine().infer(signals)
    return features, signals, goal_context


@pytest.fixture
def generator() -> CandidateGenerator:
    return CandidateGenerator()


def test_candidate_count_is_within_3_to_5(generator: CandidateGenerator) -> None:
    features, signals, goal_context = run_pipeline(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    candidates = generator.generate(features, signals, goal_context)

    assert 3 <= len(candidates) <= 5


def test_no_secondary_goals_yields_exactly_3(generator: CandidateGenerator) -> None:
    empty_goal_context = GoalContext(
        primary_goal="COLLECT_REVIEWS", secondary_goals=(), rationale="x", supporting_signals=()
    )
    features, signals, _ = run_pipeline()
    candidates = generator.generate(features, signals, empty_goal_context)

    assert len(candidates) == 3
    assert {c.goal for c in candidates} == {"COLLECT_REVIEWS"}
    assert {c.compulsion_lever for c in candidates} == {
        "social_proof",
        "reciprocity",
        "asking_merchant",
    }


def test_secondary_goals_add_candidates_capped_at_5(generator: CandidateGenerator) -> None:
    goal_context = GoalContext(
        primary_goal="RECOVER_REVENUE",
        secondary_goals=("REDUCE_CHURN", "PROMOTE_OFFERS", "IMPROVE_LISTINGS", "COLLECT_REVIEWS"),
        rationale="x",
        supporting_signals=(),
    )
    features, signals, _ = run_pipeline()
    candidates = generator.generate(features, signals, goal_context)

    assert len(candidates) == 5  # 3 primary + 2 secondary, capped


def test_every_candidate_has_all_required_fields(generator: CandidateGenerator) -> None:
    features, signals, goal_context = run_pipeline(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    for c in generator.generate(features, signals, goal_context):
        assert isinstance(c, Candidate)
        assert c.candidate_id
        assert c.goal
        assert c.compulsion_lever in COMPULSION_LEVERS
        assert c.language in ("en", "hi", "hi-en")
        assert isinstance(c.slots, Mapping)
        assert isinstance(c.priority, int) and c.priority >= 1


def test_candidate_ids_are_unique_within_one_generation(generator: CandidateGenerator) -> None:
    features, signals, goal_context = run_pipeline(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    candidates = generator.generate(features, signals, goal_context)
    ids = [c.candidate_id for c in candidates]

    assert len(ids) == len(set(ids))


def test_priority_is_strictly_increasing_in_generation_order(generator: CandidateGenerator) -> None:
    features, signals, goal_context = run_pipeline(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    priorities = [c.priority for c in generator.generate(features, signals, goal_context)]

    assert priorities == sorted(priorities)
    assert priorities == list(range(1, len(priorities) + 1))


def test_slots_are_grounded_in_feature_set_not_hallucinated(generator: CandidateGenerator) -> None:
    merchant = make_merchant(
        identity={"name": "Unique Clinic Name", "owner_first_name": "Suresh"},
        performance={"delta_7d": {"calls_pct": -0.5}},
    )
    features, signals, goal_context = run_pipeline(merchant=merchant)
    candidates = generator.generate(features, signals, goal_context)

    for c in candidates:
        assert c.slots["merchant_name"] == "Unique Clinic Name"
        assert c.slots["owner_first_name"] == "Suresh"
        # merchant_name in every candidate's slots must be the SAME value
        # taken from the SAME FeatureSet field, not per-candidate invention.
    names = {c.slots["merchant_name"] for c in candidates}
    assert names == {"Unique Clinic Name"}


def test_recover_revenue_slots_pick_the_worse_of_calls_or_views(
    generator: CandidateGenerator,
) -> None:
    goal_context = GoalContext(
        primary_goal="RECOVER_REVENUE", secondary_goals=(), rationale="x", supporting_signals=()
    )
    features, signals, _ = run_pipeline(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.6, "views_pct": -0.1}})
    )
    candidate = generator.generate(features, signals, goal_context)[0]

    assert candidate.slots["metric_label"] == "calls"
    assert candidate.slots["metric_delta_pct"] == -0.6


def test_win_back_customers_slots_include_customer_facts(generator: CandidateGenerator) -> None:
    goal_context = GoalContext(
        primary_goal="WIN_BACK_CUSTOMERS", secondary_goals=(), rationale="x", supporting_signals=()
    )
    customer = make_customer(
        identity={"name": "Priya"}, state="lapsed_soft", relationship={"last_visit": "2025-11-01"}
    )
    features, signals, _ = run_pipeline(customer=customer)
    candidate = generator.generate(features, signals, goal_context)[0]

    assert candidate.slots["customer_name"] == "Priya"
    assert candidate.slots["customer_state"] == "lapsed_soft"


def test_language_defaults_to_merchant_languages_when_no_customer(
    generator: CandidateGenerator,
) -> None:
    goal_context = GoalContext(
        primary_goal="INCREASE_VISIBILITY", secondary_goals=(), rationale="x", supporting_signals=()
    )
    en_only = make_merchant(identity={"name": "X", "languages": ["en"]})
    hi_en = make_merchant(identity={"name": "X", "languages": ["en", "hi"]})

    f1, s1, _ = run_pipeline(merchant=en_only)
    f2, s2, _ = run_pipeline(merchant=hi_en)

    assert generator.generate(f1, s1, goal_context)[0].language == "en"
    assert generator.generate(f2, s2, goal_context)[0].language == "hi-en"


def test_language_prefers_customer_pref_when_customer_context_present(
    generator: CandidateGenerator,
) -> None:
    goal_context = GoalContext(
        primary_goal="WIN_BACK_CUSTOMERS", secondary_goals=(), rationale="x", supporting_signals=()
    )
    merchant = make_merchant(
        identity={"name": "X", "languages": ["en"]}
    )  # merchant is english-only
    customer = make_customer(identity={"name": "Priya", "language_pref": "hi-en mix"})

    features, signals, _ = run_pipeline(merchant=merchant, customer=customer)
    candidate = generator.generate(features, signals, goal_context)[0]

    assert candidate.language == "hi-en"  # customer pref wins over merchant-only "en"


def test_generation_is_deterministic(generator: CandidateGenerator) -> None:
    features, signals, goal_context = run_pipeline(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    first = generator.generate(features, signals, goal_context)
    second = generator.generate(features, signals, goal_context)

    assert first == second


def test_generate_requires_all_three_args(generator: CandidateGenerator) -> None:
    features, signals, goal_context = run_pipeline()
    with pytest.raises(TypeError):
        generator.generate(None, signals, goal_context)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        generator.generate(features, None, goal_context)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        generator.generate(features, signals, None)  # type: ignore[arg-type]


def test_from_config_loads_real_weights_yaml() -> None:
    generator = CandidateGenerator.from_config()
    goal_context = GoalContext(
        primary_goal="RECOVER_REVENUE", secondary_goals=(), rationale="x", supporting_signals=()
    )
    features, signals, _ = run_pipeline()
    candidates = generator.generate(features, signals, goal_context)

    assert {c.compulsion_lever for c in candidates} == {
        "loss_aversion",
        "specificity",
        "reciprocity",
    }


def test_unknown_goal_falls_back_to_specificity_lever(generator: CandidateGenerator) -> None:
    goal_context = GoalContext(
        primary_goal="SOME_UNMAPPED_GOAL", secondary_goals=(), rationale="x", supporting_signals=()
    )
    features, signals, _ = run_pipeline()
    candidates = generator.generate(features, signals, goal_context)

    assert len(candidates) >= 1
    assert candidates[0].compulsion_lever == "specificity"
