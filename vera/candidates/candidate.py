"""
vera.candidates.candidate — Candidate, Layer 4's output unit.

A Candidate is NOT a finished message — it's a (goal, persuasion angle,
concrete facts) triple. Turning it into an actual body string is
Phase 7/8's job (template selection + rendering). Keeping candidates
this abstract is what lets CandidateGenerator produce several
differently-angled options without needing to know anything about
template text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Candidate"]

#: challenge-brief.md §10 — the eight compulsion levers.
COMPULSION_LEVERS = (
    "specificity",
    "loss_aversion",
    "social_proof",
    "reciprocity",
    "curiosity",
    "asking_merchant",
    "single_binary_cta",
)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One candidate action: a goal pursued via one compulsion lever."""

    candidate_id: str
    goal: str
    compulsion_lever: str
    language: str  # "en" | "hi" | "hi-en"
    slots: Mapping[str, Any]  # concrete, FeatureSet-grounded facts for template rendering
    priority: (
        int  # CandidateGenerator's initial ordering hint (1 = most preferred); re-ranked in Phase 7
    )
