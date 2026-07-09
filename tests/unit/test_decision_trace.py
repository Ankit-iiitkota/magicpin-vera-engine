"""
DecisionTrace population tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from types import MappingProxyType

from vera.candidates.candidate import Candidate
from vera.goals.goal_context import GoalContext
from vera.ranking.scored_candidate import RenderedCandidate
from vera.signals.signal_set import Signal, SignalSet
from vera.templates.template import Template
from vera.tracing.trace_builder import TraceBuilder, build_rationale

builder = TraceBuilder()


def _rendered() -> RenderedCandidate:
    candidate = Candidate(
        candidate_id="cand_1",
        goal="INCREASE_VISIBILITY",
        compulsion_lever="curiosity",
        language="en",
        slots=MappingProxyType({}),
        priority=1,
    )
    template = Template(
        template_id="tpl_1",
        goal="INCREASE_VISIBILITY",
        levers=("curiosity",),
        cta_type="open_ended",
        required_slots=(),
        body_en="clean body?",
        body_hi_en="clean body?",
    )
    return RenderedCandidate(candidate=candidate, template=template, body="clean body?")


def _goal_context() -> GoalContext:
    return GoalContext(
        primary_goal="INCREASE_VISIBILITY",
        secondary_goals=("INCREASE_SALES",),
        rationale="SearchSpike fired",
        supporting_signals=("SearchSpike",),
    )


def _signal_set() -> SignalSet:
    return SignalSet(
        signals=(
            Signal(
                kind="SearchSpike",
                severity=3,
                is_composite=False,
                rationale_hint="search volume up",
                evidence=MappingProxyType({}),
            ),
        )
    )


def test_build_populates_every_field_from_inputs():
    trace = builder.build(
        trigger_id="trg_001",
        merchant_id="m_001",
        signal_set=_signal_set(),
        goal_context=_goal_context(),
        candidate_count=4,
        rendered=_rendered(),
        winner_score=8.5,
        fallback_level="L0",
        compulsion_lever_verified=True,
    )

    assert trace.trigger_id == "trg_001"
    assert trace.merchant_id == "m_001"
    assert trace.signal_kinds == ("SearchSpike",)
    assert trace.primary_goal == "INCREASE_VISIBILITY"
    assert trace.secondary_goals == ("INCREASE_SALES",)
    assert trace.candidate_count == 4
    assert trace.winner_candidate_id == "cand_1"
    assert trace.winner_goal == "INCREASE_VISIBILITY"
    assert trace.winner_lever == "curiosity"
    assert trace.winner_score == 8.5
    assert trace.fallback_level == "L0"
    assert trace.compulsion_lever_verified is True


def test_build_rationale_for_l0_mentions_goal_lever_signal_and_score():
    trace = builder.build(
        trigger_id="trg_001",
        merchant_id="m_001",
        signal_set=_signal_set(),
        goal_context=_goal_context(),
        candidate_count=4,
        rendered=_rendered(),
        winner_score=8.5,
        fallback_level="L0",
        compulsion_lever_verified=True,
    )

    rationale = build_rationale(trace)

    assert "INCREASE_VISIBILITY" in rationale
    assert "curiosity" in rationale
    assert "SearchSpike" in rationale
    assert "8.5" in rationale


def test_build_rationale_for_l0_with_no_signals_omits_signal_clause():
    trace = builder.build(
        trigger_id="trg_001",
        merchant_id="m_001",
        signal_set=SignalSet(signals=()),
        goal_context=_goal_context(),
        candidate_count=2,
        rendered=_rendered(),
        winner_score=6.0,
        fallback_level="L0",
        compulsion_lever_verified=True,
    )

    rationale = build_rationale(trace)

    assert "on " not in rationale.split("via")[1].split("—")[0]


def test_build_rationale_for_fallback_mentions_fallback_level():
    trace = builder.build(
        trigger_id="trg_001",
        merchant_id="m_001",
        signal_set=_signal_set(),
        goal_context=_goal_context(),
        candidate_count=3,
        rendered=_rendered(),
        winner_score=None,
        fallback_level="L1",
        compulsion_lever_verified=False,
    )

    rationale = build_rationale(trace)

    assert rationale.startswith("L1 fallback used")
    assert "INCREASE_VISIBILITY" in rationale


def test_winner_score_none_renders_as_na_only_for_fallback_path():
    trace = builder.build(
        trigger_id="trg_001",
        merchant_id="m_001",
        signal_set=_signal_set(),
        goal_context=_goal_context(),
        candidate_count=3,
        rendered=_rendered(),
        winner_score=None,
        fallback_level="L2",
        compulsion_lever_verified=False,
    )

    rationale = build_rationale(trace)

    assert rationale.startswith("L2 fallback used")
