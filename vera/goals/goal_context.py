"""
vera.goals.goal_context — GoalContext, Layer 3's output.

Layer 3 (goal inference) consumes ONLY SignalSet (Layer 2's output) —
never FeatureSet or raw context — keeping the same strict layering
FeatureSet and SignalSet already established: each layer depends only
on the layer directly beneath it.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GoalContext"]

#: The complete, canonical goal vocabulary. Every GoalContext.primary_goal
#: and every entry in secondary_goals is one of these — see
#: goal_definitions.yaml for the signal -> goal mapping.
CANONICAL_GOALS = (
    "RECOVER_REVENUE",
    "WIN_BACK_CUSTOMERS",
    "REDUCE_CHURN",
    "PROMOTE_OFFERS",
    "IMPROVE_LISTINGS",
    "COLLECT_REVIEWS",
    "INCREASE_SALES",
    "INCREASE_VISIBILITY",
)

#: Used when no rule matches (SignalSet empty or nothing recognised) —
#: a safe, generically-useful default rather than an error, since "no
#: urgent signal fired" is a normal, expected state, not a failure.
DEFAULT_GOAL = "INCREASE_VISIBILITY"


@dataclass(frozen=True, slots=True)
class GoalContext:
    """What this message should accomplish, and why."""

    primary_goal: str
    secondary_goals: tuple[str, ...]
    rationale: str
    supporting_signals: tuple[str, ...]  # signal kinds that led to primary_goal
