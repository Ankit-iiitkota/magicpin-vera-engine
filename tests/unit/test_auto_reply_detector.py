"""
WA auto-reply pattern tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from vera.conversation.auto_reply_detector import AutoReplyDetector

detector = AutoReplyDetector()

# Contains a known canned phrase — phrase detection catches it on sight.
_CANNED = "We are currently unavailable. We will get back to you soon."

# No canned phrasing — only the verbatim-repeat rule can catch this one.
_REPEATED = "Namaste, shop is open 10am to 9pm daily."


def test_canned_phrasing_is_auto_reply_on_first_sight():
    # challenge-brief.md §3 pain point 1: production Vera burns 2-3 turns
    # before detecting an auto-reply; phrase detection must not wait for
    # the repeat threshold.
    assert detector.is_auto_reply([], _CANNED) is True


def test_no_prior_messages_is_not_auto_reply():
    assert detector.is_auto_reply([], _REPEATED) is False


def test_single_prior_match_is_not_yet_auto_reply():
    assert detector.is_auto_reply([_REPEATED], _REPEATED) is False


def test_two_prior_matches_is_auto_reply():
    assert detector.is_auto_reply([_REPEATED, _REPEATED], _REPEATED) is True


def test_matching_is_case_and_whitespace_insensitive():
    prior = [_REPEATED.upper(), "  " + _REPEATED.lower() + "  "]
    assert detector.is_auto_reply(prior, _REPEATED) is True


def test_distinct_messages_do_not_count_as_repeats():
    prior = ["Hello there", "Thanks for reaching out"]
    assert detector.is_auto_reply(prior, _REPEATED) is False


def test_repeats_of_a_different_message_do_not_trigger():
    prior = [_REPEATED, _REPEATED]
    assert detector.is_auto_reply(prior, "This is a genuine new reply") is False
