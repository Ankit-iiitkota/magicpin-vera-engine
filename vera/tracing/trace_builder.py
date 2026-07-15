"""
vera.tracing.trace_builder — DecisionTrace, an internal debug artifact.

Never returned by the API (see vera/tracing/__init__.py) — compose()
builds one on every call, logs it via structlog for observability, and
derives the short, human-readable `rationale` string that DOES go in
the API response from it. Captures the "why" behind every pipeline
decision: which signals fired, which goal won, how many candidates
were generated, which one won and at what score, and which fallback
level (if any) was needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.goals.goal_context import GoalContext
    from vera.ranking.scored_candidate import RenderedCandidate
    from vera.signals.signal_set import SignalSet

__all__ = ["DecisionTrace", "TraceBuilder", "build_rationale"]


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    trigger_id: str
    merchant_id: str
    signal_kinds: tuple[str, ...]
    primary_goal: str
    secondary_goals: tuple[str, ...]
    candidate_count: int
    winner_candidate_id: str
    winner_goal: str
    winner_lever: str
    winner_score: float | None  # None for L1/L2 fallback (not scored against candidates)
    fallback_level: str  # "L0" | "L1" | "L2"
    compulsion_lever_verified: bool


class TraceBuilder:
    def build(
        self,
        *,
        trigger_id: str,
        merchant_id: str,
        signal_set: SignalSet,
        goal_context: GoalContext,
        candidate_count: int,
        rendered: RenderedCandidate,
        winner_score: float | None,
        fallback_level: str,
        compulsion_lever_verified: bool,
    ) -> DecisionTrace:
        return DecisionTrace(
            trigger_id=trigger_id,
            merchant_id=merchant_id,
            signal_kinds=tuple(s.kind for s in signal_set.signals),
            primary_goal=goal_context.primary_goal,
            secondary_goals=goal_context.secondary_goals,
            candidate_count=candidate_count,
            winner_candidate_id=rendered.candidate.candidate_id,
            winner_goal=rendered.candidate.goal,
            winner_lever=rendered.candidate.compulsion_lever,
            winner_score=winner_score,
            fallback_level=fallback_level,
            compulsion_lever_verified=compulsion_lever_verified,
        )


def build_rationale(trace: DecisionTrace) -> str:
    """One short, human-readable sentence — this IS returned by the API."""
    if trace.fallback_level != "L0":
        return (
            f"{trace.fallback_level} fallback used — no ranked candidate cleared validation "
            f"(goal: {trace.primary_goal}, {trace.candidate_count} candidates tried)."
        )

    signal_part = f" on {trace.signal_kinds[0]}" if trace.signal_kinds else ""
    score_part = f"{trace.winner_score:.1f}/10" if trace.winner_score is not None else "n/a"
    return (
        f"{trace.winner_goal} via {trace.winner_lever}{signal_part} — "
        f"ranked highest ({score_part}) among {trace.candidate_count} candidates."
    )
