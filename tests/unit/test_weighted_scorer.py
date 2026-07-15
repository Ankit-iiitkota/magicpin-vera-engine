"""
Weighted scorer unit tests.

Hand-built RenderedCandidate instances against real FeatureSet/
GoalContext fixtures, so each dimension scorer is tested in isolation
from template-selection/rendering mechanics.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from tests.conftest import extract_features, make_category, make_merchant
from vera.candidates.candidate import Candidate
from vera.goals import GoalContext
from vera.ranking.scored_candidate import RenderedCandidate
from vera.ranking.weighted_scorer import WeightedScorer
from vera.templates.template import Template


def make_candidate(**overrides) -> Candidate:
    defaults = {
        "candidate_id": "c1",
        "goal": "RECOVER_REVENUE",
        "compulsion_lever": "specificity",
        "language": "en",
        "slots": MappingProxyType({}),
        "priority": 1,
    }
    defaults.update(overrides)
    return Candidate(**defaults)


def make_template(**overrides) -> Template:
    defaults = {
        "template_id": "t1",
        "goal": "RECOVER_REVENUE",
        "levers": ("specificity",),
        "cta_type": "open_ended",
        "required_slots": (),
        "body_en": "x",
        "body_hi_en": "x",
    }
    defaults.update(overrides)
    return Template(**defaults)


def make_rendered(
    body: str, *, cta_type: str = "open_ended", **candidate_overrides
) -> RenderedCandidate:
    candidate = make_candidate(**candidate_overrides)
    template = make_template(cta_type=cta_type)
    return RenderedCandidate(candidate=candidate, template=template, body=body)


@pytest.fixture
def scorer() -> WeightedScorer:
    return WeightedScorer()


@pytest.fixture
def goal_context() -> GoalContext:
    return GoalContext(
        primary_goal="RECOVER_REVENUE",
        secondary_goals=("PROMOTE_OFFERS",),
        rationale="x",
        supporting_signals=(),
    )


def test_specificity_rewards_numeric_density(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    features = extract_features()
    numeric = scorer.score(
        make_rendered("Calls dropped 50% this week, from 20 to 10."), features, goal_context
    )
    vague = scorer.score(make_rendered("Your numbers are down a bit."), features, goal_context)

    assert numeric.specificity > vague.specificity


def test_specificity_rewards_locality_mention(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    merchant = make_merchant(identity={"name": "X", "locality": "Andheri West"})
    features = extract_features(merchant=merchant)
    with_locality = scorer.score(
        make_rendered("Merchants in Andheri West are doing well."), features, goal_context
    )
    without = scorer.score(
        make_rendered("Merchants nearby are doing well."), features, goal_context
    )

    assert with_locality.specificity > without.specificity


def test_category_fit_penalises_taboo_vocabulary(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    category = make_category(
        voice={"tone": "peer_clinical", "vocab_taboo": ["guaranteed", "miracle"]}
    )
    features = extract_features(category=category)
    clean = scorer.score(make_rendered("Worth a look this week."), features, goal_context)
    taboo = scorer.score(
        make_rendered("This is a guaranteed miracle result."), features, goal_context
    )

    assert clean.category_fit > taboo.category_fit


def test_merchant_fit_rewards_name_presence(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    merchant = make_merchant(identity={"name": "Unique Clinic", "owner_first_name": "Suresh"})
    features = extract_features(merchant=merchant)
    with_name = scorer.score(make_rendered("Suresh, quick update for you."), features, goal_context)
    without_name = scorer.score(make_rendered("Quick update for you."), features, goal_context)

    assert with_name.merchant_fit > without_name.merchant_fit


def test_trigger_relevance_favours_primary_over_secondary_over_neither(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    features = extract_features()
    primary = scorer.score(make_rendered("x", goal="RECOVER_REVENUE"), features, goal_context)
    secondary = scorer.score(make_rendered("x", goal="PROMOTE_OFFERS"), features, goal_context)
    neither = scorer.score(make_rendered("x", goal="COLLECT_REVIEWS"), features, goal_context)

    assert primary.trigger_relevance > secondary.trigger_relevance > neither.trigger_relevance


def test_engagement_compulsion_reflects_lever_bonus_and_binary_cta(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    features = extract_features()
    high_bonus_binary = scorer.score(
        make_rendered("x", compulsion_lever="social_proof", cta_type="binary"),
        features,
        goal_context,
    )
    low_bonus_open = scorer.score(
        make_rendered("x", compulsion_lever="curiosity", cta_type="open_ended"),
        features,
        goal_context,
    )

    assert high_bonus_binary.engagement_compulsion > low_bonus_open.engagement_compulsion


def test_language_match_rewards_hindi_markers_for_hi_en_candidates(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    features = extract_features()
    matching = scorer.score(
        make_rendered("Aapke calls kam hue hai is hafte.", language="hi-en"), features, goal_context
    )
    mismatched = scorer.score(
        make_rendered("Your calls dropped this week.", language="hi-en"), features, goal_context
    )

    assert matching.language_match > mismatched.language_match


def test_total_is_weighted_sum_within_0_to_10(
    scorer: WeightedScorer, goal_context: GoalContext
) -> None:
    features = extract_features()
    scored = scorer.score(make_rendered("Calls dropped 50% this week."), features, goal_context)

    assert 0.0 <= scored.total <= 10.0


def test_scoring_is_deterministic(scorer: WeightedScorer, goal_context: GoalContext) -> None:
    features = extract_features()
    rendered = make_rendered("Calls dropped 50% this week.")
    assert scorer.score(rendered, features, goal_context) == scorer.score(
        rendered, features, goal_context
    )


def test_score_requires_all_args(scorer: WeightedScorer, goal_context: GoalContext) -> None:
    features = extract_features()
    rendered = make_rendered("x")
    with pytest.raises(TypeError):
        scorer.score(None, features, goal_context)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        scorer.score(rendered, None, goal_context)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        scorer.score(rendered, features, None)  # type: ignore[arg-type]


def test_category_and_trigger_overrides_change_the_weighting() -> None:
    scorer = WeightedScorer(
        global_weights={
            "specificity": 0.5,
            "category_fit": 0.1,
            "merchant_fit": 0.1,
            "trigger_relevance": 0.1,
            "engagement_compulsion": 0.1,
            "language_match": 0.1,
        },
        category_overrides={
            "dentists": {
                "specificity": 0.1,
                "category_fit": 0.5,
                "merchant_fit": 0.1,
                "trigger_relevance": 0.1,
                "engagement_compulsion": 0.1,
                "language_match": 0.1,
            }
        },
    )
    weights = scorer._resolve_weights("dentists", "unmapped_trigger_kind")
    assert weights["category_fit"] == 0.5  # category override applied, not global default


def test_constructor_rejects_weights_not_summing_to_one() -> None:
    with pytest.raises(ValueError, match="sum to"):
        WeightedScorer(global_weights={"specificity": 0.5, "category_fit": 0.1})


def test_from_config_loads_real_weights_yaml() -> None:
    scorer = WeightedScorer.from_config()
    features = extract_features()
    goal_context = GoalContext(
        primary_goal="RECOVER_REVENUE", secondary_goals=(), rationale="x", supporting_signals=()
    )
    scored = scorer.score(make_rendered("Calls dropped 50% this week."), features, goal_context)
    assert 0.0 <= scored.total <= 10.0
