"""
Language rule tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

import pytest

from vera.rules.language_rules import pick_language


@pytest.mark.parametrize(
    ("merchant_languages", "expected"),
    [
        (("en", "hi"), "hi-en"),
        (("hi",), "hi"),
        (("en",), "en"),
        ((), "en"),
    ],
)
def test_merchant_only_language_selection(merchant_languages, expected):
    assert pick_language(merchant_languages, None) == expected


def test_customer_pref_wins_over_merchant_languages():
    assert pick_language(("en",), "hi") == "hi"
    assert pick_language(("hi",), "en") == "en"


@pytest.mark.parametrize("pref", ["hi-en", "ta-en", "te-en", "kn-en", "mr-en"])
def test_customer_pref_regional_code_mix_maps_to_hi_en(pref):
    assert pick_language(("en",), pref) == "hi-en"


@pytest.mark.parametrize("pref", ["ta", "te", "kn", "mr"])
def test_customer_pref_regional_only_maps_to_hi(pref):
    assert pick_language(("en",), pref) == "hi"


def test_customer_pref_is_case_insensitive():
    assert pick_language(("en",), "HI-EN") == "hi-en"


def test_empty_customer_pref_string_falls_back_to_merchant_languages():
    assert pick_language(("hi",), "") == "hi"
