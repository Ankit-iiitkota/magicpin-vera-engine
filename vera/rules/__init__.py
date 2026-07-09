"""CTA / language / send-as / suppression-key resolution rules."""

from __future__ import annotations

from vera.rules.cta_rules import resolve_cta
from vera.rules.language_rules import pick_language
from vera.rules.rule_engine import MessageRules, RuleEngine
from vera.rules.send_as_rules import resolve_send_as
from vera.rules.suppression_rules import resolve_suppression_key

__all__ = [
    "MessageRules",
    "RuleEngine",
    "pick_language",
    "resolve_cta",
    "resolve_send_as",
    "resolve_suppression_key",
]
