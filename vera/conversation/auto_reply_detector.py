"""
vera.conversation.auto_reply_detector — AutoReplyDetector.

challenge-brief.md's own hint: "same message verbatim 3+ times = auto-
reply." Compares the incoming message against the merchant-authored
turns already in a conversation's history; if the exact same text
(normalised for whitespace/case) has already appeared twice before,
this occurrence is the 3rd — a WhatsApp Business canned auto-reply, not
a real human reply.
"""

from __future__ import annotations

__all__ = ["AutoReplyDetector"]

_REPEAT_THRESHOLD = 2  # this many PRIOR identical messages -> the new one is the 3rd+


class AutoReplyDetector:
    def is_auto_reply(self, prior_merchant_messages: list[str], new_message: str) -> bool:
        normalised_new = self._normalise(new_message)
        prior_matches = sum(
            1 for msg in prior_merchant_messages if self._normalise(msg) == normalised_new
        )
        return prior_matches >= _REPEAT_THRESHOLD

    @staticmethod
    def _normalise(text: str) -> str:
        return " ".join(text.strip().lower().split())
