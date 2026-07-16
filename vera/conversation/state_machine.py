"""
vera.conversation.state_machine — ConversationStateMachine.

Decides the next reply action ("send" | "wait" | "end") from a
ConversationState + the merchant's latest message. Ties
AutoReplyDetector + IntentClassifier + ReplyComposer together —
consumes only ConversationState (Phase 1/2's persisted turn history)
and the merchant's language, never raw context.

Precedence (first match decides): auto-reply pattern > hostile > decline
> wait-requested > commit > off-topic > neutral. "end" never carries a
body (challenge-testing-brief.md §2.3's ReplyEndResponse has none) — a
de-escalation/nudge attempt is always a "send" on ITS turn, with "end"
reserved for the NEXT turn if the same problem repeats. That matches
challenge-brief.md Pattern B: Vera tries once, then stops.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vera.conversation.auto_reply_detector import AutoReplyDetector
from vera.conversation.grounded_replies import commit_reply, continue_reply
from vera.conversation.intent_classifier import IntentClassifier
from vera.conversation.reply_composer import ReplyComposer

if TYPE_CHECKING:
    from vera.conversation.reply_facts import ReplyFacts
    from vera.store.conversation_store import ConversationState

__all__ = ["ConversationStateMachine", "ReplyDecision"]

_DEFAULT_MAX_TURNS = 5
_DEFAULT_WAIT_SECONDS = 1800  # 30 min


@dataclass(frozen=True, slots=True)
class ReplyDecision:
    action: str  # "send" | "wait" | "end"
    body: str | None
    cta: str | None
    wait_seconds: int | None
    rationale: str
    engagement_tag: str | None  # recorded on the persisted turn, for repeat-detection next time


class ConversationStateMachine:
    def __init__(
        self,
        auto_reply_detector: AutoReplyDetector | None = None,
        intent_classifier: IntentClassifier | None = None,
        reply_composer: ReplyComposer | None = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
        wait_seconds: int = _DEFAULT_WAIT_SECONDS,
    ) -> None:
        self._auto_reply_detector = auto_reply_detector or AutoReplyDetector()
        self._intent_classifier = intent_classifier or IntentClassifier()
        self._reply_composer = reply_composer or ReplyComposer()
        self._max_turns = max_turns
        self._wait_seconds = wait_seconds

    def decide(
        self,
        state: ConversationState,
        message: str,
        turn_number: int,
        language: str,
        facts: ReplyFacts | None = None,
    ) -> ReplyDecision:
        if state is None:
            raise TypeError("state is required")

        prior_merchant_messages = [t["body"] for t in state.turns if t.get("from") == "merchant"]

        if self._auto_reply_detector.is_auto_reply(prior_merchant_messages, message):
            if self._already_tried(state, "auto_reply_nudge"):
                return ReplyDecision(
                    action="end",
                    body=None,
                    cta=None,
                    wait_seconds=None,
                    rationale="repeated auto-reply detected after one nudge attempt — exiting gracefully",
                    engagement_tag=None,
                )
            return ReplyDecision(
                action="send",
                body=self._reply_composer.auto_reply_nudge(language),
                cta="open_ended",
                wait_seconds=None,
                rationale="auto-reply pattern detected (same message repeated) — trying once more before exiting",
                engagement_tag="auto_reply_nudge",
            )

        intent = self._intent_classifier.classify(message)

        # A question about THIS conversation's trigger (film speeds for a
        # DCI regulation, slots for a recall, ...) is on-topic even when it
        # contains none of the classifier's generic keywords — reclassify it
        # as neutral so it gets a grounded answer, not an off-topic brushoff.
        if intent == "off_topic" and facts is not None and self._mentions_topic(message, facts):
            intent = "neutral"

        if intent == "hostile":
            if self._already_tried(state, "hostile_deescalate"):
                return ReplyDecision(
                    action="end",
                    body=None,
                    cta=None,
                    wait_seconds=None,
                    rationale="hostility repeated after de-escalation attempt — exiting gracefully",
                    engagement_tag=None,
                )
            return ReplyDecision(
                action="send",
                body=self._reply_composer.hostile_deescalate(language),
                cta="none",
                wait_seconds=None,
                rationale="hostile message detected — de-escalating politely, staying on-mission",
                engagement_tag="hostile_deescalate",
            )

        if intent == "decline":
            return ReplyDecision(
                action="end",
                body=None,
                cta=None,
                wait_seconds=None,
                rationale="merchant signalled not interested — exiting gracefully",
                engagement_tag=None,
            )

        if turn_number >= self._max_turns:
            return ReplyDecision(
                action="end",
                body=None,
                cta=None,
                wait_seconds=None,
                rationale=f"reached max_turns={self._max_turns} — exiting gracefully",
                engagement_tag=None,
            )

        if intent == "wait_requested":
            return ReplyDecision(
                action="wait",
                body=None,
                cta=None,
                wait_seconds=self._wait_seconds,
                rationale="merchant asked for time; backing off",
                engagement_tag="wait_ack",
            )

        if intent == "commit":
            # Grounded first: confirm the SPECIFIC deliverable this
            # conversation's trigger promised, with its real numbers/dates.
            # The generic composer line is only the no-context fallback.
            body = commit_reply(language, facts) or self._reply_composer.commit_confirmation(
                language
            )
            return ReplyDecision(
                action="send",
                body=body,
                cta="open_ended",
                wait_seconds=None,
                rationale="explicit commitment detected — switching straight to action, not re-qualifying",
                engagement_tag="commit_confirmation",
            )

        if intent == "off_topic":
            return ReplyDecision(
                action="send",
                body=self._reply_composer.off_topic_redirect(language),
                cta="none",
                wait_seconds=None,
                rationale="off-topic question detected — staying polite and on-mission",
                engagement_tag="off_topic_redirect",
            )

        # Neutral/technical follow-up: answer with the conversation's own
        # trigger facts (regulation summary, dip numbers, review quote, ...)
        # instead of a content-free "what next?".
        body = continue_reply(language, facts) or self._reply_composer.continue_conversation(
            language
        )
        return ReplyDecision(
            action="send",
            body=body,
            cta="open_ended",
            wait_seconds=None,
            rationale="neutral engaged reply — continuing with the trigger's own facts",
            engagement_tag="continue",
        )

    @staticmethod
    def _already_tried(state: ConversationState, engagement_tag: str) -> bool:
        return any(t.get("engagement") == engagement_tag for t in state.turns)

    _TOPIC_STOPWORDS = frozenset(
        {
            "what", "which", "when", "where", "will", "would", "should", "could",
            "have", "does", "this", "that", "there", "please", "want", "need",
            "know", "about", "with", "from", "your", "yours", "mera", "kaise",
            "kya", "karna", "hona", "chahiye", "batao", "more", "much", "many",
        }
    )

    @classmethod
    def _mentions_topic(cls, message: str, facts: ReplyFacts) -> bool:
        corpus = facts.topic_text
        if not corpus:
            return False
        words = {w for w in re.findall(r"[a-z]{4,}", message.lower())}
        return any(w in corpus for w in words - cls._TOPIC_STOPWORDS)
