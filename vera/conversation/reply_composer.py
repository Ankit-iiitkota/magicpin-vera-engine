"""
vera.conversation.reply_composer — ReplyComposer.

Generates the actual body text for each reply-turn outcome. Kept
deliberately simple and safe: unlike compose() (Phase 8's main
pipeline, grounded in a full FeatureSet), a mid-conversation reply only
has the merchant's language reliably available — so these messages
never cite a number, date, or fact that wasn't already sent in the
opening message. No hallucination risk because there's nothing here to
hallucinate from.

No method here composes a farewell/goodbye body: challenge-testing-
brief.md §2.3's ReplyEndResponse has no `body` field at all — "end"
carries only a rationale. ConversationStateMachine reflects that: it
always sends a de-escalation/nudge attempt as a "send" on its own turn,
and only returns "end" (body=None) on a LATER turn if the same problem
repeats.
"""

from __future__ import annotations

__all__ = ["ReplyComposer"]


class ReplyComposer:
    def auto_reply_nudge(self, language: str) -> str:
        if language in ("hi", "hi-en"):
            return (
                "Samajh gayi. Team tak pahunchane se pehle, kya aap khud dekhna "
                "chahengi ki exact kya update karna hai? 2 minute ka kaam hai. Chalega?"
            )
        return "Got it. Before this goes to your team, want to take a quick look yourself? It's a 2-minute check."

    def hostile_deescalate(self, language: str) -> str:
        if language in ("hi", "hi-en"):
            return "Maaf kijiye agar mera message pareshaan karne wala laga. Main sirf madad karne ki koshish kar rahi thi."
        return "Sorry if that came across the wrong way — I was only trying to help. I'll leave it there for now."

    def wait_ack(self, language: str) -> str:
        if language in ("hi", "hi-en"):
            return "Bilkul, koi jaldi nahi hai. Main baad mein check karungi."
        return "No rush at all — I'll check back later."

    def commit_confirmation(self, language: str) -> str:
        """challenge-brief.md Pattern D: a commit must switch straight to action, never re-qualify."""
        if language in ("hi", "hi-en"):
            return "Badhiya, aage badh rahi hoon — 2 minute mein update kar deti hoon aur yahin bata dungi."
        return "Great, moving ahead now — I'll have it updated in a couple of minutes and confirm right here."

    def off_topic_redirect(self, language: str) -> str:
        if language in ("hi", "hi-en"):
            return (
                "Yeh mera area nahi hai, is mein zyada madad nahi kar paungi — lekin "
                "aapki listing/offers ke baare mein kuch bhi ho toh zaroor batayein."
            )
        return "That's outside what I can help with, but happy to keep going on your listing or offers whenever you're ready."

    def continue_conversation(self, language: str) -> str:
        if language in ("hi", "hi-en"):
            return "Samajh gayi — bataiye, aage kya karna chahenge?"
        return "Got it — what would you like to do next?"
