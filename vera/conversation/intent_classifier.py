"""
vera.conversation.intent_classifier — IntentClassifier.

Deterministic, keyword/regex classification of a merchant's reply text
into one of six intents, checked in this precedence order (a message
can match more than one category; the first match wins):

  1. hostile        — abusive language (challenge-testing-brief.md §4
                       Phase 4 "hostile/off-topic" replay scenario)
  2. decline         — explicit not-interested / stop, without abuse
  3. wait_requested  — merchant asked for time
  4. commit          — explicit "yes"/"let's do it"/"go ahead"
                       (challenge-brief.md's Pattern D: a commit must
                       switch straight to action, never re-qualify)
  5. off_topic       — a question that doesn't mention anything in
                       Vera's actual mission (offers/listing/reviews/...)
  6. neutral         — none of the above; a normal engaged reply
"""

from __future__ import annotations

import re

__all__ = ["IntentClassifier"]

_HOSTILE_RE = re.compile(
    r"\b(spam|useless|stupid|shut up|rubbish|nonsense|harass\w*)\b", re.IGNORECASE
)
_DECLINE_RE = re.compile(
    r"\b(not interested|no thanks|unsubscribe|leave me alone|stop|nahi chahiye)\b", re.IGNORECASE
)
_WAIT_RE = re.compile(r"\b(later|busy|not now|give me time|abhi nahi|baad mein)\b", re.IGNORECASE)
_COMMIT_RE = re.compile(
    r"\b(yes|lets do it|let's do it|go ahead|sounds good|please proceed|confirm|sure|ok go|haan|theek hai|chalo)\b",
    re.IGNORECASE,
)
_ON_TOPIC_RE = re.compile(
    r"\b(offer|listing|profile|review|post|gbp|customer|price|discount|campaign|visibility|google)\w*",
    re.IGNORECASE,
)


class IntentClassifier:
    def classify(self, message: str) -> str:
        if not message or not message.strip():
            return "neutral"
        if _HOSTILE_RE.search(message):
            return "hostile"
        if _DECLINE_RE.search(message):
            return "decline"
        if _WAIT_RE.search(message):
            return "wait_requested"
        if _COMMIT_RE.search(message):
            return "commit"
        if "?" in message and not _ON_TOPIC_RE.search(message):
            return "off_topic"
        return "neutral"
