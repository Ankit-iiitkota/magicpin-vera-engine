"""
vera.ranking.weighted_scorer — WeightedScorer.

Scores a RenderedCandidate against the same 5-dimension rubric the
external judge uses (challenge-brief.md §8): specificity, category_fit,
merchant_fit, trigger_relevance, engagement_compulsion — plus
language_match, tracked separately for debuggability. This is our OWN
internal, deterministic heuristic proxy used only to pick the best of
OUR generated candidates; it doesn't need to match the external LLM
judge's semantic scoring exactly, just be a consistent, explainable
ranking signal.

Per-dimension weights come from config/weights.yaml: global defaults,
overridden per-category, then nudged per-trigger-kind (additive delta)
— exactly the "Category overrides" / "Trigger overrides" this phase
asks for.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vera.config import load_yaml
from vera.ranking.scored_candidate import ScoredCandidate

if TYPE_CHECKING:
    from vera.features.feature_set import FeatureSet
    from vera.goals.goal_context import GoalContext
    from vera.ranking.scored_candidate import RenderedCandidate

__all__ = ["WeightedScorer"]

_WEIGHTS_PATH = "config/weights.yaml"
_DIMENSIONS = (
    "specificity",
    "category_fit",
    "merchant_fit",
    "trigger_relevance",
    "engagement_compulsion",
    "language_match",
)
_SUM_TOLERANCE = 0.001

_DEFAULT_GLOBAL_WEIGHTS = {
    "specificity": 0.25,
    "category_fit": 0.20,
    "merchant_fit": 0.20,
    "trigger_relevance": 0.20,
    "engagement_compulsion": 0.10,
    "language_match": 0.05,
}
_DEFAULT_LEVER_BONUSES = {
    "social_proof": 0.10,
    "asking_merchant": 0.10,
    "loss_aversion": 0.08,
    "reciprocity": 0.07,
    "specificity": 0.06,
    "curiosity": 0.05,
    "single_binary_cta": 0.05,
}

_NUMERIC_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
_HI_MARKERS = ("hai", "kar", "aur", "aapke", "aapki", "hoon", "chahenge", "wala", "kya", "din")


class WeightedScorer:
    def __init__(
        self,
        global_weights: dict[str, float] | None = None,
        category_overrides: dict[str, dict[str, float]] | None = None,
        trigger_overrides: dict[str, dict[str, float]] | None = None,
        lever_bonuses: dict[str, float] | None = None,
    ) -> None:
        self._global = global_weights or dict(_DEFAULT_GLOBAL_WEIGHTS)
        self._category_overrides = category_overrides or {}
        self._trigger_overrides = trigger_overrides or {}
        self._lever_bonuses = lever_bonuses or dict(_DEFAULT_LEVER_BONUSES)
        self._validate_sums_to_one("global", self._global)
        for category, weights in self._category_overrides.items():
            self._validate_sums_to_one(f"category_overrides.{category}", weights)

    @classmethod
    def from_config(cls, path: str = _WEIGHTS_PATH) -> WeightedScorer:
        data = load_yaml(path)
        return cls(
            global_weights=data.get("global"),
            category_overrides=data.get("category_overrides"),
            trigger_overrides=data.get("trigger_overrides"),
            lever_bonuses=data.get("lever_bonuses"),
        )

    @staticmethod
    def _validate_sums_to_one(name: str, weights: dict[str, float]) -> None:
        total = sum(weights.get(dim, 0.0) for dim in _DIMENSIONS)
        if abs(total - 1.0) > _SUM_TOLERANCE:
            raise ValueError(
                f"weights.yaml: {name} weights sum to {total:.4f}, expected 1.0 (±{_SUM_TOLERANCE})"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def score(
        self, rendered: RenderedCandidate, features: FeatureSet, goal_context: GoalContext
    ) -> ScoredCandidate:
        if rendered is None or features is None or goal_context is None:
            raise TypeError("rendered, features, and goal_context are all required")

        weights = self._resolve_weights(features.identity.category_slug, features.trigger.kind)

        raw = {
            "specificity": self._score_specificity(rendered, features),
            "category_fit": self._score_category_fit(rendered, features),
            "merchant_fit": self._score_merchant_fit(rendered, features),
            "trigger_relevance": self._score_trigger_relevance(rendered, goal_context),
            "engagement_compulsion": self._score_engagement_compulsion(rendered),
            "language_match": self._score_language_match(rendered),
        }
        total = sum(weights.get(dim, 0.0) * raw[dim] for dim in _DIMENSIONS)

        return ScoredCandidate(
            rendered=rendered,
            specificity=raw["specificity"],
            category_fit=raw["category_fit"],
            merchant_fit=raw["merchant_fit"],
            trigger_relevance=raw["trigger_relevance"],
            engagement_compulsion=raw["engagement_compulsion"],
            language_match=raw["language_match"],
            total=total,
        )

    # ── Weight resolution ────────────────────────────────────────────────────

    def _resolve_weights(self, category_slug: str, trigger_kind: str) -> dict[str, float]:
        weights = dict(self._global)
        weights.update(self._category_overrides.get(category_slug, {}))
        for dim, delta in self._trigger_overrides.get(trigger_kind, {}).items():
            weights[dim] = weights.get(dim, 0.0) + delta
        return weights

    # ── Dimension scorers — each returns a 0-10 raw score ──────────────────────

    @staticmethod
    def _score_specificity(rendered: RenderedCandidate, features: FeatureSet) -> float:
        numeric_tokens = len(_NUMERIC_TOKEN_RE.findall(rendered.body))
        score = 3.0 + numeric_tokens * 2.5
        if features.identity.locality and features.identity.locality in rendered.body:
            score += 1.0
        return min(10.0, score)

    @staticmethod
    def _score_category_fit(rendered: RenderedCandidate, features: FeatureSet) -> float:
        lowered = rendered.body.lower()
        taboo_hits = sum(1 for word in features.category.vocab_taboo if word.lower() in lowered)
        return max(0.0, 10.0 - taboo_hits * 3.0)

    @staticmethod
    def _score_merchant_fit(rendered: RenderedCandidate, features: FeatureSet) -> float:
        name_hit = bool(
            (
                features.identity.owner_first_name
                and features.identity.owner_first_name in rendered.body
            )
            or (features.identity.name and features.identity.name in rendered.body)
        )
        return 10.0 if name_hit else 6.0

    @staticmethod
    def _score_trigger_relevance(rendered: RenderedCandidate, goal_context: GoalContext) -> float:
        goal = rendered.candidate.goal
        if goal == goal_context.primary_goal:
            return 10.0
        if goal in goal_context.secondary_goals:
            return 6.0
        return 3.0

    def _score_engagement_compulsion(self, rendered: RenderedCandidate) -> float:
        bonus = self._lever_bonuses.get(rendered.candidate.compulsion_lever, 0.0)
        score = 5.0 + bonus * 50.0
        if rendered.template.cta_type == "binary":
            score += 1.0
        return min(10.0, score)

    @staticmethod
    def _score_language_match(rendered: RenderedCandidate) -> float:
        lowered = rendered.body.lower()
        has_hi_markers = any(marker in lowered for marker in _HI_MARKERS)
        if rendered.candidate.language in ("hi", "hi-en"):
            return 10.0 if has_hi_markers else 4.0
        return 10.0 if not has_hi_markers else 6.0
