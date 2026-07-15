"""
Intent classification tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

import pytest

from vera.conversation.intent_classifier import IntentClassifier

classifier = IntentClassifier()


@pytest.mark.parametrize(
    "message",
    ["This is spam", "You're useless", "Stop harassing me", "This is nonsense"],
)
def test_hostile_messages_are_classified_hostile(message):
    assert classifier.classify(message) == "hostile"


@pytest.mark.parametrize(
    "message",
    ["Not interested, thanks", "No thanks", "Please unsubscribe me", "nahi chahiye"],
)
def test_decline_messages_are_classified_decline(message):
    assert classifier.classify(message) == "decline"


@pytest.mark.parametrize(
    "message",
    ["I'm busy right now", "Ask me later", "Give me time please", "abhi nahi"],
)
def test_wait_messages_are_classified_wait_requested(message):
    assert classifier.classify(message) == "wait_requested"


@pytest.mark.parametrize(
    "message",
    ["Yes, let's do it", "Sure, go ahead", "haan, theek hai", "Sounds good, please proceed"],
)
def test_commit_messages_are_classified_commit(message):
    assert classifier.classify(message) == "commit"


def test_off_topic_question_without_mission_keywords_is_off_topic():
    assert classifier.classify("What's the weather like today?") == "off_topic"


def test_question_with_mission_keyword_is_not_off_topic():
    assert classifier.classify("Can you tell me about the review campaign?") == "neutral"


def test_plain_statement_with_no_keywords_is_neutral():
    assert classifier.classify("Okay, thanks for letting me know") == "neutral"


def test_empty_message_is_neutral():
    assert classifier.classify("") == "neutral"
    assert classifier.classify("   ") == "neutral"


def test_hostile_takes_precedence_over_off_topic_question():
    assert classifier.classify("This is useless, why do you keep messaging?") == "hostile"


def test_decline_takes_precedence_over_wait():
    assert classifier.classify("Not interested, maybe later") == "decline"
