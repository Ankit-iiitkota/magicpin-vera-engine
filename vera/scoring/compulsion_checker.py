"""
vera.scoring.compulsion_checker — CompulsionChecker.

A candidate CLAIMS a compulsion_lever (Phase 6), but nothing before
this point verifies the rendered text actually reads that way. This
does a lightweight keyword/pattern check per lever, covering both
English and the Hindi-English markers our hi-en template bodies
actually use — not because the templates are untrusted (they were
hand-written to match their declared lever), but as a regression
guard: if a future template edit drifts away from its lever, this
catches it deterministically instead of only an external judge
noticing.

Deliberately advisory, not a hard gate: it's a keyword approximation,
not a semantic judgment, so FallbackChain logs it into the decision
trace / rationale rather than rejecting a candidate over it. Structural
problems (OutputValidator, AntiPatternDetector) ARE hard gates —
those catch objectively wrong output, this catches "does this read a
bit differently than the label suggests", which is worth knowing but
not worth cascading to a lower-ranked candidate over.
"""

from __future__ import annotations

import re

__all__ = ["CompulsionChecker"]

_LEVER_PATTERNS: dict[str, re.Pattern[str]] = {
    "specificity": re.compile(r"\d"),
    "loss_aversion": re.compile(
        r"\b(before|risk|losing|miss\w*|lapsing|lapse|drop|declin\w*|compound\w*|cost\w*"
        r"|giravat|nuksan|kam ho\w*)\b",
        re.IGNORECASE,
    ),
    "social_proof": re.compile(
        r"\b(merchants|peers|most|customers|others|demand|trend\w*|searches|wave)\b", re.IGNORECASE
    ),
    "curiosity": re.compile(
        r"\b(want to see|curious|worth a look|want the|dekhna chahenge|chahenge)\b|\?",
        re.IGNORECASE,
    ),
    "reciprocity": re.compile(
        r"\b(i've|already|go ahead|i have|drafted|maine|taiyar|nikal liye|kar diya)\b",
        re.IGNORECASE,
    ),
    "asking_merchant": re.compile(r"\?"),
    "single_binary_cta": re.compile(
        r"\b(yes|reply\s+(yes|no|\d)|go ahead|go\b|bolein)\b", re.IGNORECASE
    ),
}


class CompulsionChecker:
    def check(self, body: str, claimed_lever: str) -> bool:
        """True if `body` textually exhibits `claimed_lever`. Unknown levers pass (no false block)."""
        pattern = _LEVER_PATTERNS.get(claimed_lever)
        if pattern is None:
            return True
        return bool(pattern.search(body))
