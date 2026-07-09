"""
vera.templates.template — Template, the unit TemplateRegistry indexes.

A Template is a Jinja2 body (one variant per language) plus the
metadata TemplateSelector needs to score how well it fits a given
Candidate: which goal/levers it was written for, which slots it
requires to render sensibly, and its CTA shape.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Template"]


@dataclass(frozen=True, slots=True)
class Template:
    template_id: str
    goal: str  # one of vera.goals.CANONICAL_GOALS, or "*" for goal-agnostic fallbacks
    levers: tuple[str, ...]  # compulsion levers this body was written to express
    cta_type: str  # "binary" | "open_ended" | "none"
    required_slots: tuple[str, ...]  # slots that must be non-None for this template to make sense
    body_en: str  # Jinja2 source, English
    body_hi_en: str  # Jinja2 source, Hindi-English code-mixed
    is_fallback: bool = False
    fallback_level: int = (
        0  # 0 = normal goal template; 1 = L1 category fallback; 2 = L2 shared fallback
    )
    #: A category slug (e.g. "dentists") this body was written for, or
    #: "*" for a category-agnostic body. TemplateSelector prefers a
    #: category match, so a candidate whose merchant is in that category
    #: gets this body instead of the generic one for the same goal.
    category: str = "*"

    def body_for(self, language: str) -> str:
        """hi/hi-en candidates get the code-mixed body; everything else gets English."""
        return self.body_hi_en if language in ("hi", "hi-en") else self.body_en
