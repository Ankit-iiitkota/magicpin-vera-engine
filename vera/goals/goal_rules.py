"""
vera.goals.goal_rules — GoalRules: loads + validates goal_definitions.yaml.

Kept separate from GoalInferenceEngine so the rule TABLE (declarative,
YAML-driven — unlike Phase 4's signal detectors, which need real
conditionals over dates/thresholds, this is a pure signal-kind
membership test, so YAML is the right amount of machinery here) has
its own well-defined, independently testable load/validate step.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vera.config import load_yaml
from vera.goals.goal_context import CANONICAL_GOALS

__all__ = ["GoalRule", "GoalRules"]

# Anchored to this file's own location, not the process's working
# directory — see vera.templates.template_registry's _PACKAGE_DIR
# comment for why a bare relative string here is fragile.
_DEFINITIONS_PATH = str(Path(__file__).resolve().parent / "yaml" / "goal_definitions.yaml")


@dataclass(frozen=True, slots=True)
class GoalRule:
    goal: str
    priority: int
    requires_any: tuple[str, ...]


# Mirrors goal_definitions.yaml exactly — used when no YAML file is
# available, same "zero file I/O required" rationale as
# FeatureExtractor/SignalDetector's literal defaults.
_FALLBACK_RULES: tuple[dict[str, Any], ...] = (
    {"goal": "RECOVER_REVENUE", "priority": 1, "requires_any": ["RevenueDrop"]},
    {
        "goal": "WIN_BACK_CUSTOMERS",
        "priority": 2,
        "requires_any": ["CustomerRecall", "UrgentWinback"],
    },
    {
        "goal": "REDUCE_CHURN",
        "priority": 3,
        "requires_any": ["CampaignFatigue", "DormantMerchant", "StaleAndFatigued"],
    },
    {"goal": "PROMOTE_OFFERS", "priority": 4, "requires_any": ["OfferExpiry", "InventoryRisk"]},
    {"goal": "IMPROVE_LISTINGS", "priority": 5, "requires_any": ["ListingIncomplete"]},
    {"goal": "COLLECT_REVIEWS", "priority": 6, "requires_any": ["ReviewOpportunity"]},
    {
        "goal": "INCREASE_SALES",
        "priority": 7,
        "requires_any": [
            "WeekendOpportunity",
            "FestivalWindow",
            "LocalDemand",
            "WeatherOpportunity",
            "GrowthMomentum",
        ],
    },
    {
        "goal": "INCREASE_VISIBILITY",
        "priority": 8,
        "requires_any": ["SearchSpike", "ResearchInsight", "CompetitionOpportunity"],
    },
)


class GoalRules:
    """A validated, priority-sorted list of signal-kind -> goal rules."""

    def __init__(self, raw_rules: list[dict[str, Any]] | None = None) -> None:
        rules_data = raw_rules if raw_rules else list(_FALLBACK_RULES)
        self._rules = tuple(
            sorted((self._validate(r) for r in rules_data), key=lambda r: r.priority)
        )

    @classmethod
    def from_config(cls, path: str = _DEFINITIONS_PATH) -> GoalRules:
        data = load_yaml(path)
        return cls(data.get("rules"))

    @property
    def rules(self) -> tuple[GoalRule, ...]:
        return self._rules

    @staticmethod
    def _validate(raw: dict[str, Any]) -> GoalRule:
        goal = raw.get("goal")
        if goal not in CANONICAL_GOALS:
            raise ValueError(
                f"goal_definitions.yaml: unknown goal {goal!r} (not in CANONICAL_GOALS)"
            )
        priority = raw.get("priority")
        if not isinstance(priority, int):
            raise ValueError(f"goal_definitions.yaml: rule for {goal!r} is missing an int priority")
        requires_any = tuple(raw.get("requires_any") or ())
        if not requires_any:
            raise ValueError(f"goal_definitions.yaml: rule for {goal!r} has an empty requires_any")
        return GoalRule(goal=goal, priority=priority, requires_any=requires_any)
