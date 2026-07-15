"""
Layer 2 — Signal Detection.

Consumes FeatureSet only (Phase 3's output) — never raw context.
"""

from __future__ import annotations

from vera.signals.signal_detector import SignalDetector
from vera.signals.signal_set import Signal, SignalSet

__all__ = ["Signal", "SignalDetector", "SignalSet"]
