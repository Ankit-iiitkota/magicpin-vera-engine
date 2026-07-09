"""
vera.signals.signal_set — Signal and SignalSet.

Signals operate ONLY on FeatureSet (Phase 3's output) — never on raw
CategoryContext/MerchantContext/TriggerContext/CustomerContext. This
mirrors FeatureSet's own rule: every layer past feature extraction
consumes only the layer directly beneath it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Signal", "SignalSet"]


@dataclass(frozen=True, slots=True)
class Signal:
    """One detected condition, with the evidence that justified it."""

    kind: str  # e.g. "RevenueDrop" — matches a key in signal_definitions.yaml
    severity: int  # 1-5, from signal_definitions.yaml
    is_composite: bool
    rationale_hint: str  # short, human-readable — feeds into candidate/template rationale
    evidence: Mapping[str, Any]  # the FeatureSet values that triggered it, for tracing


@dataclass(frozen=True, slots=True)
class SignalSet:
    """Every signal that fired for one FeatureSet, most-severe first."""

    signals: tuple[Signal, ...]

    def has(self, kind: str) -> bool:
        return any(s.kind == kind for s in self.signals)

    def get(self, kind: str) -> Signal | None:
        return next((s for s in self.signals if s.kind == kind), None)

    def kinds(self) -> frozenset[str]:
        return frozenset(s.kind for s in self.signals)

    @property
    def is_empty(self) -> bool:
        return not self.signals

    @property
    def top(self) -> Signal | None:
        """The single highest-severity signal, or None if nothing fired."""
        return self.signals[0] if self.signals else None
