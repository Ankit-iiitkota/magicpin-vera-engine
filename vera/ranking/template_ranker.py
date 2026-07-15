"""
vera.ranking.template_ranker — TemplateSelector: template compatibility
scoring + selection.

For a given Candidate, scores every Template in its goal's pool (falling
back to the L1/L2 fallback templates if the pool is empty) on how well
it fits: goal match, category match, lever match, language availability,
and whether the candidate's slots actually satisfy the template's
required_slots. Picks the highest-scoring template, tie-broken by
template_id so selection is fully deterministic.

The category bonus outweighs a single lever mismatch (2.5 > 2.0) but
not a goal mismatch or two missing required slots — a category-specific
body for this merchant's business type is preferred even if it wasn't
written for this exact lever, but never at the cost of answering the
wrong goal or leaving required facts blank.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.candidates.candidate import Candidate
    from vera.templates.template import Template
    from vera.templates.template_registry import TemplateRegistry

__all__ = ["TemplateSelector"]

_GOAL_MATCH_SCORE = 3.0
_CATEGORY_MATCH_SCORE = 2.5
_LEVER_MATCH_SCORE = 2.0
_LANGUAGE_MATCH_SCORE = 1.0
_MISSING_REQUIRED_SLOT_PENALTY = 1.5


class TemplateSelector:
    def select(self, candidate: Candidate, registry: TemplateRegistry) -> Template:
        if candidate is None or registry is None:
            raise TypeError("candidate and registry are both required")

        pool = registry.for_goal(candidate.goal)
        if not pool:
            pool = registry.fallbacks()
        if not pool:
            raise ValueError("TemplateRegistry has no templates for this goal and no fallbacks")

        scored = [(self.compatibility(candidate, t), t) for t in pool]
        scored.sort(key=lambda pair: (-pair[0], pair[1].template_id))
        return scored[0][1]

    @staticmethod
    def compatibility(candidate: Candidate, template: Template) -> float:
        """Higher is better. Deterministic — same (candidate, template) always scores the same."""
        score = 0.0
        if template.goal == candidate.goal or template.goal == "*":
            score += _GOAL_MATCH_SCORE
        if template.category != "*" and template.category == candidate.slots.get("category_slug"):
            score += _CATEGORY_MATCH_SCORE
        if candidate.compulsion_lever in template.levers:
            score += _LEVER_MATCH_SCORE
        # Every template has both an en and hi_en body (Template.body_for
        # always resolves), so language never disqualifies a template —
        # it only nudges preference towards more goal/lever-specific ones.
        score += _LANGUAGE_MATCH_SCORE

        missing_required = sum(
            1 for slot in template.required_slots if candidate.slots.get(slot) is None
        )
        score -= missing_required * _MISSING_REQUIRED_SLOT_PENALTY

        return score
