"""
Anti-pattern detection tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from vera.scoring.anti_patterns import AntiPatternDetector

detector = AntiPatternDetector()


def test_clean_single_cta_message_has_no_issues():
    body = "Your dentists listing is missing 3 photos. Want me to draft the update for you?"
    assert detector.detect(body) == []


def test_generic_flat_percent_off_is_flagged():
    body = "Run a flat 20% off deal this week — reply yes to launch it?"
    issues = detector.detect(body)
    assert any("percentage-off" in i for i in issues)


def test_promotional_hype_tone_is_flagged():
    body = "This is an amazing deal, act now before it's gone!"
    issues = detector.detect(body)
    assert any("promotional" in i for i in issues)


def test_long_preamble_is_flagged():
    body = "I hope you're doing well. Here's an update about your listing."
    issues = detector.detect(body)
    assert any("preamble" in i for i in issues)


def test_multiple_question_marks_flagged_as_multiple_ctas():
    body = "Want to update your offer? Should I also refresh your listing?"
    issues = detector.detect(body)
    assert any("multiple CTAs" in i for i in issues)


def test_multiple_reply_style_ctas_flagged():
    body = "Reply yes to confirm. Or reply no to skip this one."
    issues = detector.detect(body)
    assert any("multiple CTAs" in i for i in issues)


def test_buried_cta_not_in_final_sentence_is_flagged():
    body = "Should I update your listing? I'll also check your offers while I'm at it."
    issues = detector.detect(body)
    assert any("buried CTA" in i for i in issues)


def test_cta_in_final_sentence_is_not_buried():
    body = "Your offer expires in 2 days. Want me to renew it for you?"
    issues = detector.detect(body)
    assert not any("buried CTA" in i for i in issues)


def test_multiple_issues_can_stack():
    body = (
        "I hope you're doing well. This is an amazing deal — flat 20% off! Reply yes or reply no?"
    )
    issues = detector.detect(body)
    assert len(issues) >= 3
