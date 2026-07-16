"""
vera.conversation.auto_reply_detector — AutoReplyDetector.

Two independent detections:

1. Verbatim repetition — challenge-brief.md's own hint: "same message
   verbatim 3+ times = auto-reply." If the exact same text (normalised
   for whitespace/case) already appeared before in this conversation's
   merchant-authored turns, the new occurrence is canned.
2. Canned phrasing — WhatsApp Business auto-replies are formulaic
   ("Thank you for contacting us…", "hamari team tak pahuncha…").
   Production Vera's biggest time sink is burning 2-3 turns before the
   repeat threshold trips (challenge-brief.md §3 pain point 1); phrase
   detection catches these on the FIRST message.
"""

from __future__ import annotations

__all__ = ["AutoReplyDetector"]

_REPEAT_THRESHOLD = 2  # this many PRIOR identical messages -> the new one is the 3rd+

_CANNED_PHRASES = (
    "thank you for contacting",
    "thanks for contacting",
    "our team will respond",
    "we will get back to you",
    "we'll get back to you",
    "this is an automated",
    "i am an automated",
    "automated assistant",
    "auto-reply",
    "aapki jaankari ke liye bahut",
    "hamari team tak pahuncha",
    "main ek automated",
)


class AutoReplyDetector:
    def is_auto_reply(self, prior_merchant_messages: list[str], new_message: str) -> bool:
        normalised_new = self._normalise(new_message)
        if any(phrase in normalised_new for phrase in _CANNED_PHRASES):
            return True
        prior_matches = sum(
            1 for msg in prior_merchant_messages if self._normalise(msg) == normalised_new
        )
        return prior_matches >= _REPEAT_THRESHOLD

    @staticmethod
    def _normalise(text: str) -> str:
        return " ".join(text.strip().lower().split())
