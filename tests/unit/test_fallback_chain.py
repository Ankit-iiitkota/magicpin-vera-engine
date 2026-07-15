"""
FallbackChain L1/L2/L3 tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from tests.conftest import extract_features
from vera.candidates.candidate import Candidate
from vera.fallback.fallback_chain import FallbackChain
from vera.ranking.scored_candidate import RenderedCandidate, ScoredCandidate
from vera.templates.template import Template
from vera.templates.template_registry import TemplateRegistry


def make_candidate(**overrides) -> Candidate:
    data = {
        "candidate_id": "cand_1",
        "goal": "INCREASE_VISIBILITY",
        "compulsion_lever": "curiosity",
        "language": "en",
        "slots": MappingProxyType({}),
        "priority": 1,
    }
    data.update(overrides)
    return Candidate(**data)


def make_template(**overrides) -> Template:
    data = {
        "template_id": "tpl_1",
        "goal": "INCREASE_VISIBILITY",
        "levers": ("curiosity",),
        "cta_type": "open_ended",
        "required_slots": (),
        "body_en": "clean body",
        "body_hi_en": "clean body",
        "is_fallback": False,
        "fallback_level": 0,
    }
    data.update(overrides)
    return Template(**data)


def make_scored(body: str, template: Template | None = None, total: float = 5.0) -> ScoredCandidate:
    template = template or make_template()
    rendered = RenderedCandidate(candidate=make_candidate(), template=template, body=body)
    return ScoredCandidate(
        rendered=rendered,
        specificity=1.0,
        category_fit=1.0,
        merchant_fit=1.0,
        trigger_relevance=1.0,
        engagement_compulsion=1.0,
        language_match=1.0,
        total=total,
    )


def make_registry(
    l1_body: str | None = "clean l1 body?", l2_body: str = "clean l2 body?"
) -> TemplateRegistry:
    templates = []
    if l1_body is not None:
        templates.append(
            make_template(
                template_id="fallback_l1",
                is_fallback=True,
                fallback_level=1,
                body_en=l1_body,
                body_hi_en=l1_body,
            )
        )
    templates.append(
        make_template(
            template_id="fallback_l2",
            is_fallback=True,
            fallback_level=2,
            body_en=l2_body,
            body_hi_en=l2_body,
        )
    )
    return TemplateRegistry(tuple(templates))


def test_first_clean_ranked_candidate_wins_as_l0():
    chain = FallbackChain(make_registry())
    ranked = (make_scored("A clean message. Want an update?"),)
    features = extract_features()

    rendered, level = chain.resolve(ranked, features)

    assert level == "L0"
    assert rendered.body == "A clean message. Want an update?"


def test_second_ranked_candidate_wins_when_first_fails_validation():
    chain = FallbackChain(make_registry())
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    good = make_scored("A clean message. Want an update?")
    features = extract_features()

    rendered, level = chain.resolve((bad, good), features)

    assert level == "L0"
    assert rendered.body == good.rendered.body


def test_falls_back_to_l1_when_every_ranked_candidate_fails():
    chain = FallbackChain(make_registry(l1_body="Clean fallback check-in. Want a quick update?"))
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    features = extract_features()

    rendered, level = chain.resolve((bad,), features)

    assert level == "L1"
    assert rendered.template.fallback_level == 1


def test_falls_back_to_l2_when_l1_also_fails():
    chain = FallbackChain(make_registry(l1_body="amazing deal, act now!", l2_body="Clean L2 body?"))
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    features = extract_features()

    rendered, level = chain.resolve((bad,), features)

    assert level == "L2"
    assert rendered.template.fallback_level == 2


def test_l2_is_returned_even_if_it_would_fail_validation():
    chain = FallbackChain(
        make_registry(l1_body="amazing deal, act now!", l2_body="amazing deal, act now!")
    )
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    features = extract_features()

    rendered, level = chain.resolve((bad,), features)

    assert level == "L2"


def test_empty_ranked_raises_value_error():
    chain = FallbackChain(make_registry())
    with pytest.raises(ValueError):
        chain.resolve((), extract_features())


def test_none_features_raises_type_error():
    chain = FallbackChain(make_registry())
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    with pytest.raises(TypeError):
        chain.resolve((bad,), None)


def test_exhausted_chain_raises_runtime_error_when_no_fallback_templates_exist():
    chain = FallbackChain(TemplateRegistry(()))
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    with pytest.raises(RuntimeError):
        chain.resolve((bad,), extract_features())


def test_from_config_loads_real_fallback_templates():
    chain = FallbackChain.from_config()
    bad = make_scored("Flat 20% off — reply yes or reply no?")
    rendered, level = chain.resolve((bad,), extract_features())

    assert level in ("L1", "L2")
    assert rendered.body
