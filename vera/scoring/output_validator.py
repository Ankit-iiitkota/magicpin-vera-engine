"""
vera.scoring.output_validator — OutputValidator.

Structural sanity gate on the final composed message: non-empty body,
a sane length ceiling (challenge-brief.md sets no hard cap, but a
runaway-template bug producing a 5000-character body is a bug, not a
feature), and valid enum values for cta/send_as. Returns a list of
issues (empty = clean) rather than raising, so callers (FallbackChain)
can decide what to do about a failure.
"""

from __future__ import annotations

__all__ = ["OutputValidator"]

_VALID_CTA = ("binary", "open_ended", "none")
_VALID_SEND_AS = ("vera", "merchant_on_behalf")
_MAX_BODY_LENGTH = 1000


class OutputValidator:
    def validate(self, body: str, cta: str, send_as: str, suppression_key: str) -> list[str]:
        issues: list[str] = []

        if not body or not body.strip():
            issues.append("body is empty")
        elif len(body) > _MAX_BODY_LENGTH:
            issues.append(f"body exceeds {_MAX_BODY_LENGTH} characters ({len(body)})")

        if cta not in _VALID_CTA:
            issues.append(f"invalid cta: {cta!r} (must be one of {_VALID_CTA})")

        if send_as not in _VALID_SEND_AS:
            issues.append(f"invalid send_as: {send_as!r} (must be one of {_VALID_SEND_AS})")

        if not suppression_key or not suppression_key.strip():
            issues.append("suppression_key is empty")

        return issues
