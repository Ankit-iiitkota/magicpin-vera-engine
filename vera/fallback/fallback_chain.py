"""
vera.fallback.fallback_chain — FallbackChain, the three-level safety net.

L0: the ranked candidates from Phase 7, in order — the first one that
    passes OutputValidator + AntiPatternDetector wins (these are the
    objective, structural gates: non-empty, sane length, valid enum
    values, no generic-discount/promotional/preamble/multi-CTA/
    buried-CTA anti-patterns).
L1: a category-flavoured generic check-in (still uses salutation()'s
    per-category voice) — used only if every ranked candidate fails L0.
L2: an absolute last-resort, fully generic template — used only if L1
    also fails. Always returned, never itself gated (there's nowhere
    left to fall back to).

Entirely synchronous — no store access. Suppression and anti-repetition
are separate, async, store-backed concerns the API layer applies
before/after calling into this (see vera.engine.suppression /
vera.engine.anti_repetition) — they decide whether to act on a trigger
at all, not which candidate to pick once composing has started.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from vera.candidates.candidate import Candidate
from vera.ranking.scored_candidate import RenderedCandidate
from vera.rules.language_rules import pick_language
from vera.scoring.anti_patterns import AntiPatternDetector
from vera.scoring.output_validator import OutputValidator
from vera.templates.template_engine import TemplateEngine
from vera.templates.template_registry import TemplateRegistry

if TYPE_CHECKING:
    from vera.features.feature_set import FeatureSet
    from vera.ranking.scored_candidate import ScoredCandidate
    from vera.templates.template import Template

__all__ = ["FallbackChain"]

_PLACEHOLDER_SEND_AS = "vera"
_PLACEHOLDER_SUPPRESSION_KEY = "fallback-check"
_FALLBACK_PRIORITY = 999


class FallbackChain:
    def __init__(
        self,
        registry: TemplateRegistry,
        engine: TemplateEngine | None = None,
        output_validator: OutputValidator | None = None,
        anti_pattern_detector: AntiPatternDetector | None = None,
    ) -> None:
        self._registry = registry
        self._engine = engine or TemplateEngine()
        self._output_validator = output_validator or OutputValidator()
        self._anti_pattern_detector = anti_pattern_detector or AntiPatternDetector()

    @classmethod
    def from_config(cls) -> FallbackChain:
        return cls(TemplateRegistry.from_directories())

    def resolve(
        self, ranked: tuple[ScoredCandidate, ...], features: FeatureSet
    ) -> tuple[RenderedCandidate, str]:
        """Returns (rendered, level) where level is "L0" | "L1" | "L2"."""
        if not ranked:
            raise ValueError("ranked must be non-empty")
        if features is None:
            raise TypeError("features is required")

        for scored in ranked:
            if not self._issues(scored.rendered.body, scored.rendered.template.cta_type):
                return scored.rendered, "L0"

        l1 = self._render_fallback_level(features, level=1)
        if l1 is not None and not self._issues(l1.body, l1.template.cta_type):
            return l1, "L1"

        l2 = self._render_fallback_level(features, level=2)
        if l2 is not None:
            return l2, "L2"

        raise RuntimeError("FallbackChain exhausted: no L0/L1/L2 candidate available")

    def _issues(self, body: str, cta_type: str) -> list[str]:
        return self._output_validator.validate(
            body, cta_type, _PLACEHOLDER_SEND_AS, _PLACEHOLDER_SUPPRESSION_KEY
        ) + self._anti_pattern_detector.detect(body)

    def _render_fallback_level(
        self, features: FeatureSet, *, level: int
    ) -> RenderedCandidate | None:
        pool = self._registry.fallback_at_level(level)
        if not pool:
            return None
        template = pool[0]
        candidate = self._fallback_candidate(features, template)
        body = self._engine.render(template, candidate)
        return RenderedCandidate(candidate=candidate, template=template, body=body)

    @staticmethod
    def _fallback_candidate(features: FeatureSet, template: Template) -> Candidate:
        slots = MappingProxyType(
            {
                "merchant_name": features.identity.name,
                "owner_first_name": features.identity.owner_first_name,
                "category_slug": features.identity.category_slug,
                "locality": features.identity.locality,
                "city": features.identity.city,
            }
        )
        cr = features.customer_relationship
        language = pick_language(
            features.identity.languages,
            cr.customer_language_pref if cr.has_customer_context else None,
        )
        return Candidate(
            candidate_id=f"fallback_{template.template_id}_{features.trigger.id}",
            goal=template.goal,
            compulsion_lever=template.levers[0] if template.levers else "curiosity",
            language=language,
            slots=slots,
            priority=_FALLBACK_PRIORITY,
        )
