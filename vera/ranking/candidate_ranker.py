"""
vera.ranking.candidate_ranker — CandidateRanker.

Ties TemplateSelector (compatibility scoring), TemplateEngine
(rendering), and WeightedScorer (the 5-dimension rubric) together:
for every Candidate, pick its best-fit template, render it, score it,
then sort deterministically and pick the winner.

Tie-breaking (applied whenever two ScoredCandidates have the exact
same total): lower candidate.priority wins (CandidateGenerator's own
ordering — primary-goal candidates before secondary-goal ones), then
candidate_id lexical order as the final, always-decisive tiebreaker.
Same inputs always produce the same winner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.ranking.scored_candidate import RenderedCandidate
from vera.ranking.template_ranker import TemplateSelector
from vera.ranking.weighted_scorer import WeightedScorer
from vera.templates.template_engine import TemplateEngine
from vera.templates.template_registry import TemplateRegistry

if TYPE_CHECKING:
    from vera.candidates.candidate import Candidate
    from vera.features.feature_set import FeatureSet
    from vera.goals.goal_context import GoalContext
    from vera.ranking.scored_candidate import ScoredCandidate

__all__ = ["CandidateRanker"]


class CandidateRanker:
    def __init__(
        self,
        registry: TemplateRegistry,
        selector: TemplateSelector | None = None,
        engine: TemplateEngine | None = None,
        scorer: WeightedScorer | None = None,
    ) -> None:
        self._registry = registry
        self._selector = selector or TemplateSelector()
        self._engine = engine or TemplateEngine()
        self._scorer = scorer or WeightedScorer()

    @classmethod
    def from_config(cls, weights_path: str = "config/weights.yaml") -> CandidateRanker:
        registry = TemplateRegistry.from_directories()
        scorer = WeightedScorer.from_config(weights_path)
        return cls(registry, scorer=scorer)

    def rank(
        self, candidates: tuple[Candidate, ...], features: FeatureSet, goal_context: GoalContext
    ) -> tuple[ScoredCandidate, ...]:
        if not candidates:
            raise ValueError("candidates must be non-empty")
        if features is None or goal_context is None:
            raise TypeError("features and goal_context are both required")

        scored = []
        for candidate in candidates:
            template = self._selector.select(candidate, self._registry)
            body = self._engine.render(template, candidate)
            rendered = RenderedCandidate(candidate=candidate, template=template, body=body)
            scored.append(self._scorer.score(rendered, features, goal_context))

        return tuple(
            sorted(
                scored,
                key=lambda sc: (
                    -sc.total,
                    sc.rendered.candidate.priority,
                    sc.rendered.candidate.candidate_id,
                ),
            )
        )

    def pick_winner(
        self, candidates: tuple[Candidate, ...], features: FeatureSet, goal_context: GoalContext
    ) -> ScoredCandidate:
        return self.rank(candidates, features, goal_context)[0]
