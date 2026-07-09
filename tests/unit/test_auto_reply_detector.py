"""
WA auto-reply pattern tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from vera.conversation.auto_reply_detector import AutoReplyDetector

detector = AutoReplyDetector()

_CANNED = "We are currently unavailable. We will get back to you soon."


def test_no_prior_messages_is_not_auto_reply():
    assert detector.is_auto_reply([], _CANNED) is False


def test_single_prior_match_is_not_yet_auto_reply():
    assert detector.is_auto_reply([_CANNED], _CANNED) is False


def test_two_prior_matches_is_auto_reply():
    assert detector.is_auto_reply([_CANNED, _CANNED], _CANNED) is True


def test_matching_is_case_and_whitespace_insensitive():
    prior = [_CANNED.upper(), "  " + _CANNED.lower() + "  "]
    assert detector.is_auto_reply(prior, _CANNED) is True


def test_distinct_messages_do_not_count_as_repeats():
    prior = ["Hello there", "Thanks for reaching out"]
    assert detector.is_auto_reply(prior, _CANNED) is False


def test_repeats_of_a_different_message_do_not_trigger():
    prior = [_CANNED, _CANNED]
    assert detector.is_auto_reply(prior, "This is a genuine new reply") is False
