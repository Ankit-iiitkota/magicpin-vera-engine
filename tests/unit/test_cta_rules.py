"""
CTA rule selection tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

import pytest

from vera.rules.cta_rules import HIGH_URGENCY_THRESHOLD, resolve_cta


def test_none_cta_type_always_wins_regardless_of_urgency():
    assert resolve_cta("none", trigger_urgency=5) == "none"
    assert resolve_cta("none", trigger_urgency=1) == "none"


@pytest.mark.parametrize("template_cta_type", ["open_ended", "binary"])
def test_high_urgency_forces_binary(template_cta_type):
    assert resolve_cta(template_cta_type, trigger_urgency=HIGH_URGENCY_THRESHOLD) == "binary"
    assert resolve_cta(template_cta_type, trigger_urgency=5) == "binary"


def test_low_urgency_keeps_template_cta_type():
    assert resolve_cta("open_ended", trigger_urgency=1) == "open_ended"
    assert resolve_cta("binary", trigger_urgency=1) == "binary"


def test_urgency_just_below_threshold_keeps_template_cta_type():
    assert resolve_cta("open_ended", trigger_urgency=HIGH_URGENCY_THRESHOLD - 1) == "open_ended"
