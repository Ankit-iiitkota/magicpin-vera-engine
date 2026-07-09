"""
vera.scoring.anti_patterns — AntiPatternDetector.

Deterministic, regex/keyword checks for the anti-patterns
challenge-brief.md §11 explicitly calls out: generic percentage-off
copy, multiple CTAs in one message, a buried call-to-action, and
promotional/hype tone in categories that need a peer/clinical voice.
Returns a list of issues (empty = clean).
"""

from __future__ import annotations

import re

__all__ = ["AntiPatternDetector"]

_GENERIC_DISCOUNT_RE = re.compile(r"\bflat\s+\d+%\s*off\b", re.IGNORECASE)
_PROMOTIONAL_RE = re.compile(
    r"\b(amazing deal|best in city|guaranteed|miracle|act now|limited time only)\b", re.IGNORECASE
)
_REPLY_CTA_RE = re.compile(r"\breply\s+(yes|no|stop|\d)", re.IGNORECASE)
_PREAMBLE_PHRASES = (
    "i hope you're doing well",
    "i hope this message finds you",
    "i am reaching out today",
    "i am writing to",
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class AntiPatternDetector:
    def detect(self, body: str) -> list[str]:
        issues: list[str] = []
        lowered = body.lower()

        if _GENERIC_DISCOUNT_RE.search(body):
            issues.append(
                "generic percentage-off discount language — prefer service+price specificity"
            )

        if _PROMOTIONAL_RE.search(body):
            issues.append("promotional/hype tone detected")

        for phrase in _PREAMBLE_PHRASES:
            if phrase in lowered:
                issues.append(f"long preamble detected: {phrase!r}")
                break

        question_marks = body.count("?")
        reply_ctas = len(_REPLY_CTA_RE.findall(body))
        if question_marks > 1 or reply_ctas > 1:
            issues.append("multiple CTAs detected in one message")

        if "?" in body:
            sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(body) if s.strip()]
            if sentences and "?" not in sentences[-1]:
                issues.append("call-to-action is not in the final sentence (buried CTA)")

        return issues
