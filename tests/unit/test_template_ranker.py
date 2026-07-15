"""
Template ranker (TemplateSelector) unit tests.

Hand-built Template/Candidate pool so compatibility scoring and
selection logic are tested independently of the real YAML content.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from vera.candidates.candidate import Candidate
from vera.ranking.template_ranker import TemplateSelector
from vera.templates.template import Template
from vera.templates.template_registry import TemplateRegistry


def make_template(**overrides) -> Template:
    defaults = {
        "template_id": "t1",
        "goal": "RECOVER_REVENUE",
        "levers": ("specificity",),
        "cta_type": "open_ended",
        "required_slots": (),
        "body_en": "body",
        "body_hi_en": "body",
    }
    defaults.update(overrides)
    return Template(**defaults)


def make_candidate(**overrides) -> Candidate:
    defaults = {
        "candidate_id": "c1",
        "goal": "RECOVER_REVENUE",
        "compulsion_lever": "specificity",
        "language": "en",
        "slots": MappingProxyType({"a": 1}),
        "priority": 1,
    }
    defaults.update(overrides)
    return Candidate(**defaults)


@pytest.fixture
def selector() -> TemplateSelector:
    return TemplateSelector()


def test_compatibility_rewards_goal_and_lever_match(selector: TemplateSelector) -> None:
    candidate = make_candidate(goal="RECOVER_REVENUE", compulsion_lever="specificity")
    matching = make_template(goal="RECOVER_REVENUE", levers=("specificity",))
    goal_only = make_template(goal="RECOVER_REVENUE", levers=("loss_aversion",))
    neither = make_template(goal="PROMOTE_OFFERS", levers=("loss_aversion",))

    assert selector.compatibility(candidate, matching) > selector.compatibility(
        candidate, goal_only
    )
    assert selector.compatibility(candidate, goal_only) > selector.compatibility(candidate, neither)


def test_compatibility_penalises_missing_required_slots(selector: TemplateSelector) -> None:
    candidate = make_candidate(slots=MappingProxyType({"needed": None}))
    strict = make_template(required_slots=("needed",))
    loose = make_template(required_slots=())

    assert selector.compatibility(candidate, loose) > selector.compatibility(candidate, strict)


def test_wildcard_goal_template_still_matches(selector: TemplateSelector) -> None:
    candidate = make_candidate(goal="RECOVER_REVENUE")
    wildcard = make_template(goal="*", levers=())
    unrelated = make_template(goal="PROMOTE_OFFERS", levers=())

    assert selector.compatibility(candidate, wildcard) > selector.compatibility(
        candidate, unrelated
    )


def test_select_picks_highest_scoring_template(selector: TemplateSelector) -> None:
    candidate = make_candidate(goal="RECOVER_REVENUE", compulsion_lever="specificity")
    best = make_template(template_id="best", goal="RECOVER_REVENUE", levers=("specificity",))
    worse = make_template(template_id="worse", goal="RECOVER_REVENUE", levers=("loss_aversion",))
    registry = TemplateRegistry((worse, best))

    assert selector.select(candidate, registry).template_id == "best"


def test_select_falls_back_to_registry_fallbacks_when_no_goal_match(
    selector: TemplateSelector,
) -> None:
    candidate = make_candidate(goal="SOME_UNKNOWN_GOAL")
    fallback = make_template(template_id="fallback", goal="*", is_fallback=True)
    unrelated = make_template(template_id="unrelated", goal="RECOVER_REVENUE")
    registry = TemplateRegistry((unrelated, fallback))

    assert selector.select(candidate, registry).template_id == "fallback"


def test_select_tie_breaks_deterministically_by_template_id(selector: TemplateSelector) -> None:
    candidate = make_candidate(goal="RECOVER_REVENUE", compulsion_lever="specificity")
    t_b = make_template(template_id="b_template", goal="RECOVER_REVENUE", levers=("specificity",))
    t_a = make_template(template_id="a_template", goal="RECOVER_REVENUE", levers=("specificity",))
    registry = TemplateRegistry((t_b, t_a))

    assert selector.select(candidate, registry).template_id == "a_template"


def test_select_raises_on_missing_args(selector: TemplateSelector) -> None:
    with pytest.raises(TypeError):
        selector.select(None, TemplateRegistry(()))  # type: ignore[arg-type]


def test_select_raises_when_registry_totally_empty(selector: TemplateSelector) -> None:
    candidate = make_candidate()
    with pytest.raises(ValueError):
        selector.select(candidate, TemplateRegistry(()))


def test_compatibility_is_deterministic(selector: TemplateSelector) -> None:
    candidate = make_candidate()
    template = make_template()
    assert selector.compatibility(candidate, template) == selector.compatibility(
        candidate, template
    )


# ── Category-aware selection ─────────────────────────────────────────────


def test_category_match_outranks_generic_template_even_on_a_weaker_lever(
    selector: TemplateSelector,
) -> None:
    candidate = make_candidate(
        goal="RECOVER_REVENUE",
        compulsion_lever="reciprocity",
        slots=MappingProxyType({"category_slug": "dentists"}),
    )
    category_specific = make_template(
        template_id="dentists_specific",
        goal="RECOVER_REVENUE",
        levers=("loss_aversion", "specificity"),
        category="dentists",
    )
    generic_exact_lever = make_template(
        template_id="generic_reciprocity",
        goal="RECOVER_REVENUE",
        levers=("reciprocity",),
        category="*",
    )

    assert selector.compatibility(candidate, category_specific) > selector.compatibility(
        candidate, generic_exact_lever
    )


def test_category_bonus_does_not_apply_to_a_different_merchant_category(
    selector: TemplateSelector,
) -> None:
    candidate = make_candidate(
        goal="RECOVER_REVENUE",
        slots=MappingProxyType({"category_slug": "salons"}),
    )
    dentists_template = make_template(goal="RECOVER_REVENUE", levers=(), category="dentists")
    generic_template = make_template(goal="RECOVER_REVENUE", levers=(), category="*")

    assert selector.compatibility(candidate, dentists_template) == selector.compatibility(
        candidate, generic_template
    )


def test_select_picks_category_specific_template_for_matching_merchant(
    selector: TemplateSelector,
) -> None:
    candidate = make_candidate(
        goal="RECOVER_REVENUE",
        compulsion_lever="specificity",
        slots=MappingProxyType({"category_slug": "gyms"}),
    )
    gyms_template = make_template(
        template_id="gyms_recover_revenue",
        goal="RECOVER_REVENUE",
        levers=("loss_aversion",),
        category="gyms",
    )
    generic_template = make_template(
        template_id="generic_recover_revenue",
        goal="RECOVER_REVENUE",
        levers=("specificity",),
        category="*",
    )
    registry = TemplateRegistry((generic_template, gyms_template))

    assert selector.select(candidate, registry).template_id == "gyms_recover_revenue"


def test_template_category_defaults_to_wildcard() -> None:
    template = make_template()
    assert template.category == "*"
