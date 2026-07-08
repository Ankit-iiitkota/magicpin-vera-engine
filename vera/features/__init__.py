"""
Layer 1 — Feature Extraction.

This package is the ONLY place in the codebase allowed to read
CategoryContext / MerchantContext / TriggerContext / CustomerContext
fields directly. Everything downstream (signals, goals, candidates,
ranking, templates, scoring, the composer) consumes FeatureSet only —
see vera.features.extractor for the full rationale.
"""

from __future__ import annotations

from vera.features.builder import FeatureBuilder
from vera.features.extractor import FeatureExtractor
from vera.features.feature_set import FeatureSet
from vera.features.validator import FeatureValidationError, FeatureValidator

__all__ = [
    "FeatureBuilder",
    "FeatureExtractor",
    "FeatureSet",
    "FeatureValidationError",
    "FeatureValidator",
]
