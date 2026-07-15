"""
vera.templates.template_engine — TemplateEngine, the Jinja2 slot-filler.

Renders a Template's body (English or Hindi-English, picked by
candidate.language) against a Candidate's slots. Every slot value
already traces to a specific FeatureSet field (see Phase 6's
candidate_generator.py) — this module's only job is turning
{merchant_name: "...", metric_delta_pct: -0.5, ...} into a finished
sentence, never inventing a fact of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import jinja2

if TYPE_CHECKING:
    from vera.candidates.candidate import Candidate
    from vera.templates.template import Template

__all__ = ["TemplateEngine", "TemplateRenderError"]


class TemplateRenderError(RuntimeError):
    """Raised when a template body fails to render against a candidate's slots."""


def _salutation(owner_first_name: str | None, category_slug: str | None) -> str:
    """Category-aware greeting name — 'Dr. Meera' for dentists, 'Meera' otherwise."""
    name = owner_first_name or "there"
    prefix = "Dr. " if category_slug == "dentists" else ""
    return f"{prefix}{name}"


def _pct(value: float | None, *, signed: bool = False) -> str:
    """Render a fraction (e.g. -0.5) as a percentage string ('-50%' / '50%')."""
    if value is None:
        return ""
    formatted = f"{value * 100:.0f}%"
    if signed and value > 0:
        formatted = f"+{formatted}"
    return formatted


def _abs_pct(value: float | None) -> str:
    """Render the magnitude of a fraction as a percentage ('50%' for both ±0.5)."""
    if value is None:
        return ""
    return f"{abs(value) * 100:.0f}%"


class TemplateEngine:
    def __init__(self) -> None:
        # finalize=... prevents a None slot from literally rendering the
        # text "None" when a template interpolates it outside a
        # conditional — None becomes an empty string instead.
        self._env = jinja2.Environment(
            finalize=lambda value: "" if value is None else value,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        self._env.filters["pct"] = _pct
        self._env.filters["abs_pct"] = _abs_pct
        self._env.globals["salutation"] = _salutation

    def render(self, template: Template, candidate: Candidate) -> str:
        source = template.body_for(candidate.language)
        try:
            jinja_template = self._env.from_string(source)
            rendered = jinja_template.render(**candidate.slots)
        except jinja2.TemplateError as exc:
            raise TemplateRenderError(
                f"failed to render template {template.template_id!r} for candidate "
                f"{candidate.candidate_id!r}: {exc}"
            ) from exc
        return self._normalise_whitespace(rendered)

    @staticmethod
    def _normalise_whitespace(text: str) -> str:
        return " ".join(text.split())
