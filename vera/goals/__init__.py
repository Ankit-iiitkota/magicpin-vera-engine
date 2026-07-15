"""
Layer 3 — Business Goal Inference.

Consumes SignalSet only (Phase 4's output) — never FeatureSet, never
raw context.
"""

from __future__ import annotations

from vera.goals.goal_context import CANONICAL_GOALS, DEFAULT_GOAL, GoalContext
from vera.goals.goal_inferrer import GoalInferenceEngine
from vera.goals.goal_rules import GoalRule, GoalRules

__all__ = [
    "CANONICAL_GOALS",
    "DEFAULT_GOAL",
    "GoalContext",
    "GoalInferenceEngine",
    "GoalRule",
    "GoalRules",
]
