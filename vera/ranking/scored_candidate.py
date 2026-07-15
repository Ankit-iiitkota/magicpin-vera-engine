"""
vera.ranking.scored_candidate — RenderedCandidate and ScoredCandidate.

RenderedCandidate is a Candidate (Phase 6) paired with the Template
(Phase 7) TemplateSelector picked for it and the body TemplateEngine
rendered from that pairing. ScoredCandidate adds the 5-dimension
rubric score from challenge-brief.md §8 (plus language_match, which
the rubric folds into merchant_fit but this pipeline tracks separately
since it's independently computable and useful for debugging).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.candidates.candidate import Candidate
    from vera.templates.template import Template

__all__ = ["RenderedCandidate", "ScoredCandidate"]


@dataclass(frozen=True, slots=True)
class RenderedCandidate:
    candidate: Candidate
    template: Template
    body: str


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    rendered: RenderedCandidate
    specificity: float
    category_fit: float
    merchant_fit: float
    trigger_relevance: float
    engagement_compulsion: float
    language_match: float
    total: float
