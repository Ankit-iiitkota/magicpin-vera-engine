"""
Layer 4 — Candidate Action Generation.

Consumes FeatureSet + SignalSet + GoalContext only — never raw context.
"""

from __future__ import annotations

from vera.candidates.candidate import COMPULSION_LEVERS, Candidate
from vera.candidates.candidate_generator import CandidateGenerator

__all__ = ["COMPULSION_LEVERS", "Candidate", "CandidateGenerator"]
