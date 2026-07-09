"""
vera.rules.cta_rules — CTA selection.

The template already carries a cta_type chosen at authoring time (see
vera/templates/yaml/shared/*.yaml), which is the right default most of
the time. The one rule this module adds on top: a high-urgency trigger
should still ask for an explicit binary commitment even if the winning
template defaulted to open-ended — challenge-brief.md's "single primary
CTA" rule doesn't say every urgent message must be binary, but urgency
>=4 (e.g. a severe revenue drop, a subscription about to lapse) is
exactly the case where forcing a clear yes/no beats leaving it open.
"""

from __future__ import annotations

__all__ = ["HIGH_URGENCY_THRESHOLD", "resolve_cta"]

HIGH_URGENCY_THRESHOLD = 4


def resolve_cta(template_cta_type: str, trigger_urgency: int) -> str:
    if template_cta_type == "none":
        return "none"
    if trigger_urgency >= HIGH_URGENCY_THRESHOLD:
        return "binary"
    return template_cta_type
