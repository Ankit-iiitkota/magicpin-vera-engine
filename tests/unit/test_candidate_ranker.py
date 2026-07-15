"""
CandidateRanker unit tests — the Phase 7 orchestrator: select template,
render, score, sort, pick winner. Runs the real pipeline
(FeatureExtractor -> SignalDetector -> GoalInferenceEngine ->
CandidateGenerator) against the real template library for realistic
end-to-end coverage.
"""

from __future__ import annotations

import pytest

from tests.conftest import extract_features, make_category, make_merchant
from vera.candidates import CandidateGenerator
from vera.goals import GoalInferenceEngine
from vera.ranking import CandidateRanker
from vera.signals import SignalDetector


def build_pipeline_inputs(**kwargs):
    features = extract_features(**kwargs)
    signals = SignalDetector().detect(features)
    goal_context = GoalInferenceEngine().infer(signals)
    candidates = CandidateGenerator().generate(features, signals, goal_context)
    return candidates, features, goal_context


@pytest.fixture
def ranker() -> CandidateRanker:
    return CandidateRanker.from_config()


def test_rank_returns_one_scored_candidate_per_input_candidate(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    ranked = ranker.rank(candidates, features, goal_context)

    assert len(ranked) == len(candidates)


def test_rank_is_sorted_descending_by_total(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    totals = [sc.total for sc in ranker.rank(candidates, features, goal_context)]

    assert totals == sorted(totals, reverse=True)


def test_pick_winner_returns_the_top_ranked_candidate(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    ranked = ranker.rank(candidates, features, goal_context)
    winner = ranker.pick_winner(candidates, features, goal_context)

    assert winner == ranked[0]


def test_winner_favours_the_primary_goal(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    winner = ranker.pick_winner(candidates, features, goal_context)

    assert winner.rendered.candidate.goal == goal_context.primary_goal


def test_ranking_is_fully_deterministic(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    first = ranker.rank(candidates, features, goal_context)
    second = ranker.rank(candidates, features, goal_context)

    assert first == second
    assert [sc.rendered.candidate.candidate_id for sc in first] == [
        sc.rendered.candidate.candidate_id for sc in second
    ]


def test_rendered_bodies_are_never_empty(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs(
        merchant=make_merchant(performance={"delta_7d": {"calls_pct": -0.5}})
    )
    for sc in ranker.rank(candidates, features, goal_context):
        assert sc.rendered.body.strip()
        assert "None" not in sc.rendered.body


def test_rank_rejects_empty_candidates(ranker: CandidateRanker) -> None:
    _, features, goal_context = build_pipeline_inputs()
    with pytest.raises(ValueError):
        ranker.rank((), features, goal_context)


def test_rank_requires_features_and_goal_context(ranker: CandidateRanker) -> None:
    candidates, features, goal_context = build_pipeline_inputs()
    with pytest.raises(TypeError):
        ranker.rank(candidates, None, goal_context)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ranker.rank(candidates, features, None)  # type: ignore[arg-type]


def test_every_category_and_every_goal_can_render_without_crashing() -> None:
    """
    Cross-product smoke test: every category x every canonical goal must
    select a template and render without raising. Catches a missing
    required_slots declaration or a template referencing a slot no
    goal's slot-builder ever provides.
    """
    from vera.goals.goal_context import CANONICAL_GOALS

    ranker = CandidateRanker.from_config()
    for category_slug in ("dentists", "salons", "restaurants", "gyms", "pharmacies"):
        category = make_category(slug=category_slug)
        merchant = make_merchant(category_slug=category_slug)
        candidates, features, goal_context = build_pipeline_inputs(
            category=category, merchant=merchant
        )
        for goal in CANONICAL_GOALS:
            from vera.goals import GoalContext

            forced_goal_context = GoalContext(
                primary_goal=goal, secondary_goals=(), rationale="x", supporting_signals=()
            )
            forced_candidates = CandidateGenerator().generate(
                features, SignalDetector().detect(features), forced_goal_context
            )
            ranked = ranker.rank(forced_candidates, features, forced_goal_context)
            assert ranked[0].rendered.body.strip()


def test_winning_template_is_category_specific_when_one_exists_for_that_goal() -> None:
    """Every (category, goal) pair this optimization pass wrote a
    category-specific template for must actually win the ranking for a
    merchant in that category — not just exist unused in the registry."""
    from vera.goals import GoalContext
    from vera.goals.goal_context import CANONICAL_GOALS

    ranker = CandidateRanker.from_config()
    for category_slug in ("dentists", "salons", "restaurants", "gyms", "pharmacies"):
        category = make_category(slug=category_slug)
        merchant = make_merchant(category_slug=category_slug)
        for goal in CANONICAL_GOALS:
            features = extract_features(category=category, merchant=merchant)
            goal_context = GoalContext(
                primary_goal=goal, secondary_goals=(), rationale="x", supporting_signals=()
            )
            candidates = CandidateGenerator().generate(
                features, SignalDetector().detect(features), goal_context
            )
            winner = ranker.pick_winner(candidates, features, goal_context)
            assert winner.rendered.template.category == category_slug, (
                f"{category_slug}/{goal} did not select its category-specific template "
                f"(got {winner.rendered.template.template_id!r})"
            )
