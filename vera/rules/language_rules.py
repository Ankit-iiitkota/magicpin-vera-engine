"""
vera.rules.language_rules — the canonical language-selection decision.

Single source of truth for "what language should this message be in":
a customer's own language_pref wins when a CustomerContext is present
(customer-facing send), otherwise it's derived from the merchant's
identity.languages. vera.candidates.candidate_generator delegates here
rather than keeping its own copy — see CandidateGenerator._pick_language.
"""

from __future__ import annotations

__all__ = ["pick_language"]

_REGIONAL_TAGS = ("hi", "ta", "te", "kn", "mr")


def pick_language(
    merchant_languages: tuple[str, ...],
    customer_language_pref: str | None = None,
) -> str:
    """Return one of "en" | "hi" | "hi-en"."""
    if customer_language_pref:
        return _normalise_customer_pref(customer_language_pref)
    return _normalise_merchant_languages(merchant_languages)


def _normalise_merchant_languages(languages: tuple[str, ...]) -> str:
    has_en = "en" in languages
    has_hi = "hi" in languages
    if has_en and has_hi:
        return "hi-en"
    if has_hi:
        return "hi"
    return "en"


def _normalise_customer_pref(pref: str) -> str:
    lowered = pref.lower()
    if "en" in lowered and any(tag in lowered for tag in _REGIONAL_TAGS):
        # Our template library only has en / hi-en copy (see Phase 7).
        # Every regional code-mix (ta-en, te-en, kn-en, mr-en) routes to
        # the hi-en *structure* as the closest available style — the
        # exact customer_language_pref string is preserved in FeatureSet
        # for future per-language template expansion; nothing here
        # discards it.
        return "hi-en"
    if lowered.startswith(_REGIONAL_TAGS) and "en" not in lowered:
        return "hi"
    return "en"
