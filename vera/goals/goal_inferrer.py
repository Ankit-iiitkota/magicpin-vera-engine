"""
vera.goals.goal_inferrer — GoalInferenceEngine, Layer 3.

GoalInferenceEngine.infer(signal_set) is the ONLY function in this
module. It consumes SignalSet only (Phase 4's output) — never
FeatureSet, never raw context — matching FeatureSet's and SignalSet's
own "consume only the layer beneath you" rule.

Every rule whose requires_any is satisfied by the fired signal kinds is
"applicable" — not just the first one found. Each applicable rule gets
a score:

    score = severity_sum + breadth_bonus + priority_bonus

  - severity_sum: sum of the fired severities of its supporting signals
    — a rule backed by more urgent evidence should be able to outrank a
    rule that's merely earlier in the priority table.
  - breadth_bonus: +0.5 per extra corroborating signal beyond the
    first — two independent signals pointing at the same goal is
    stronger evidence than one.
  - priority_bonus: a modest, deliberately sub-dominant nudge toward
    the rule table's declared business-importance order (revenue >
    churn > visibility, ...) — big enough to break near-ties the way
    the old first-match order did, small enough that a genuinely
    severe, well-corroborated signal on a "lower" goal can still win.

Deterministic: score is a pure function of the SignalSet + the fixed
rule table, and ties are broken by (priority, goal name), so the same
SignalSet always produces the same GoalContext.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.goals.goal_context import DEFAULT_GOAL, GoalContext
from vera.goals.goal_rules import GoalRules

if TYPE_CHECKING:
    from vera.goals.goal_rules import GoalRule
    from vera.signals.signal_set import SignalSet

__all__ = ["GoalInferenceEngine"]

_BREADTH_BONUS = 0.5
_PRIORITY_BONUS = 0.5


class GoalInferenceEngine:
    def __init__(self, rules: GoalRules | None = None) -> None:
        self._rules = rules if rules is not None else GoalRules()

    @classmethod
    def from_config(cls, path: str | None = None) -> GoalInferenceEngine:
        rules = GoalRules.from_config(path) if path else GoalRules.from_config()
        return cls(rules)

    def infer(self, signal_set: SignalSet) -> GoalContext:
        if signal_set is None:
            raise TypeError("signal_set is required")

        fired_kinds = signal_set.kinds()
        rule_count = len(self._rules.rules)
        scored: list[tuple[float, GoalRule, tuple[str, ...]]] = []
        for rule in self._rules.rules:
            supporting = tuple(k for k in rule.requires_any if k in fired_kinds)
            if not supporting:
                continue
            severity_sum = sum(signal_set.get(k).severity for k in supporting)
            breadth_bonus = _BREADTH_BONUS * (len(supporting) - 1)
            priority_bonus = (rule_count + 1 - rule.priority) * _PRIORITY_BONUS
            score = severity_sum + breadth_bonus + priority_bonus
            scored.append((score, rule, supporting))

        if not scored:
            return GoalContext(
                primary_goal=DEFAULT_GOAL,
                secondary_goals=(),
                rationale="No signal matched a specific goal rule; defaulting to a general engagement goal.",
                supporting_signals=(),
            )

        scored.sort(key=lambda m: (-m[0], m[1].priority, m[1].goal))
        top_score, primary_rule, primary_supporting = scored[0]
        secondary_goals = tuple(dict.fromkeys(rule.goal for _, rule, _ in scored[1:]))

        top_signal = signal_set.top
        rationale = (
            f"{primary_rule.goal} scored highest ({top_score:.1f}, priority "
            f"{primary_rule.priority}) among {len(scored)} applicable goal(s) on signal(s) "
            f"{', '.join(primary_supporting)}"
        )
        if top_signal is not None:
            rationale += (
                f" — most severe overall: {top_signal.kind} (severity {top_signal.severity})"
            )

        return GoalContext(
            primary_goal=primary_rule.goal,
            secondary_goals=secondary_goals,
            rationale=rationale,
            supporting_signals=primary_supporting,
        )
