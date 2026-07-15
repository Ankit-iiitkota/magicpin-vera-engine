"""
Template slot-fill tests.

Uses small hand-built Template/Candidate instances rather than the real
YAML content, so tests target TemplateEngine's rendering mechanics
(None-safety, filters, whitespace normalisation, language selection)
in isolation from the actual template copy.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from vera.candidates.candidate import Candidate
from vera.templates.template import Template
from vera.templates.template_engine import TemplateEngine, TemplateRenderError


def make_template(**overrides) -> Template:
    defaults = {
        "template_id": "t1",
        "goal": "RECOVER_REVENUE",
        "levers": ("specificity",),
        "cta_type": "open_ended",
        "required_slots": (),
        "body_en": "Hello {{ merchant_name }}, {{ metric }} moved {{ delta | pct }}.",
        "body_hi_en": "Namaste {{ merchant_name }}, {{ metric }} mein {{ delta | pct }} badlaav hai.",
    }
    defaults.update(overrides)
    return Template(**defaults)


def make_candidate(**overrides) -> Candidate:
    defaults = {
        "candidate_id": "c1",
        "goal": "RECOVER_REVENUE",
        "compulsion_lever": "specificity",
        "language": "en",
        "slots": MappingProxyType({"merchant_name": "Dr. Meera", "metric": "calls", "delta": -0.5}),
        "priority": 1,
    }
    defaults.update(overrides)
    return Candidate(**defaults)


@pytest.fixture
def engine() -> TemplateEngine:
    return TemplateEngine()


def test_renders_english_body_for_english_candidate(engine: TemplateEngine) -> None:
    body = engine.render(make_template(), make_candidate(language="en"))
    assert body == "Hello Dr. Meera, calls moved -50%."


def test_renders_hindi_english_body_for_hi_en_candidate(engine: TemplateEngine) -> None:
    body = engine.render(make_template(), make_candidate(language="hi-en"))
    assert body == "Namaste Dr. Meera, calls mein -50% badlaav hai."


def test_none_slot_renders_as_empty_not_the_string_none(engine: TemplateEngine) -> None:
    template = make_template(body_en="Offer: {{ suggested_offer_title }}.")
    candidate = make_candidate(slots=MappingProxyType({"suggested_offer_title": None}))

    body = engine.render(template, candidate)

    assert "None" not in body
    assert body == "Offer: ."


def test_conditional_block_hides_missing_optional_fact(engine: TemplateEngine) -> None:
    template = make_template(
        body_en="Hi{% if offer %} — check out {{ offer }}{% endif %}, want details?"
    )
    with_offer = make_candidate(slots=MappingProxyType({"offer": "Cleaning @ 299"}))
    without_offer = make_candidate(slots=MappingProxyType({"offer": None}))

    assert "Cleaning @ 299" in engine.render(template, with_offer)
    assert "check out" not in engine.render(template, without_offer)


def test_pct_filter_formats_fraction_as_percentage(engine: TemplateEngine) -> None:
    template = make_template(body_en="{{ value | pct }}")
    assert engine.render(template, make_candidate(slots=MappingProxyType({"value": 0.5}))) == "50%"
    assert (
        engine.render(template, make_candidate(slots=MappingProxyType({"value": -0.5}))) == "-50%"
    )


def test_pct_filter_signed_adds_plus_for_positive(engine: TemplateEngine) -> None:
    template = make_template(body_en="{{ value | pct(signed=true) }}")
    assert engine.render(template, make_candidate(slots=MappingProxyType({"value": 0.3}))) == "+30%"


def test_abs_pct_filter_strips_sign(engine: TemplateEngine) -> None:
    template = make_template(body_en="{{ value | abs_pct }}")
    assert (
        engine.render(template, make_candidate(slots=MappingProxyType({"value": -0.42}))) == "42%"
    )


def test_salutation_adds_dr_prefix_for_dentists(engine: TemplateEngine) -> None:
    template = make_template(body_en="{{ salutation(owner_first_name, category_slug) }}")
    dentist = make_candidate(
        slots=MappingProxyType({"owner_first_name": "Meera", "category_slug": "dentists"})
    )
    salon = make_candidate(
        slots=MappingProxyType({"owner_first_name": "Lakshmi", "category_slug": "salons"})
    )

    assert engine.render(template, dentist) == "Dr. Meera"
    assert engine.render(template, salon) == "Lakshmi"


def test_salutation_falls_back_to_there_when_name_missing(engine: TemplateEngine) -> None:
    template = make_template(body_en="{{ salutation(owner_first_name, category_slug) }}")
    candidate = make_candidate(
        slots=MappingProxyType({"owner_first_name": None, "category_slug": "salons"})
    )
    assert engine.render(template, candidate) == "there"


def test_whitespace_is_normalised() -> None:
    engine = TemplateEngine()
    template = make_template(body_en="Hello   {{ merchant_name }},\n\n  how are you?")
    body = engine.render(template, make_candidate())
    assert body == "Hello Dr. Meera, how are you?"


def test_malformed_template_raises_render_error(engine: TemplateEngine) -> None:
    template = make_template(body_en="{{ unclosed")
    with pytest.raises(TemplateRenderError):
        engine.render(template, make_candidate())


def test_rendering_is_deterministic(engine: TemplateEngine) -> None:
    template = make_template()
    candidate = make_candidate()
    assert engine.render(template, candidate) == engine.render(template, candidate)
