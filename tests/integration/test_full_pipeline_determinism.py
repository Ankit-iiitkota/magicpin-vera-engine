"""
Same inputs x3 = same output tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from tests.conftest import (
    NOW,
    extract_features,
    make_category,
    make_customer,
    make_merchant,
    make_trigger,
)
from vera.engine.composer import Composer
from vera.goals.goal_inferrer import GoalInferenceEngine
from vera.signals.signal_detector import SignalDetector


def _compose_n_times(n: int, **kwargs):
    composer = Composer()
    category = kwargs.get("category") or make_category()
    merchant = kwargs.get("merchant") or make_merchant()
    trigger = kwargs.get("trigger") or make_trigger()
    customer = kwargs.get("customer")
    return [composer.compose(category, merchant, trigger, customer, now=NOW) for _ in range(n)]


def test_compose_is_deterministic_for_identical_merchant_facing_inputs():
    results = _compose_n_times(3)

    assert results[0] == results[1] == results[2]


def test_compose_is_deterministic_for_identical_customer_facing_inputs():
    customer = make_customer()
    trigger = make_trigger(
        id="trg_recall",
        scope="customer",
        kind="customer_recall",
        customer_id="c_001",
        suppression_key="recall:c_001:6mo",
    )
    results = _compose_n_times(3, trigger=trigger, customer=customer)

    assert results[0] == results[1] == results[2]


def test_compose_is_deterministic_across_revenue_drop_scenario():
    merchant = make_merchant(performance={"window_days": 30, "views_delta_pct": -0.35})
    trigger = make_trigger(id="trg_revenue", kind="revenue_drop_alert")
    results = _compose_n_times(3, merchant=merchant, trigger=trigger)

    assert results[0] == results[1] == results[2]


def test_signal_detection_is_deterministic_given_same_features():
    detector = SignalDetector()
    features = extract_features()

    runs = [detector.detect(features) for _ in range(3)]

    assert runs[0].kinds() == runs[1].kinds() == runs[2].kinds()


def test_goal_inference_is_deterministic_given_same_signals():
    detector = SignalDetector()
    engine = GoalInferenceEngine()
    features = extract_features()
    signals = detector.detect(features)

    runs = [engine.infer(signals) for _ in range(3)]

    assert runs[0] == runs[1] == runs[2]


def test_different_now_values_can_still_be_deterministic_per_value():
    composer = Composer()
    category, merchant, trigger = make_category(), make_merchant(), make_trigger()

    first_run = [composer.compose(category, merchant, trigger, now=NOW) for _ in range(2)]
    second_run = [
        composer.compose(category, merchant, trigger, now=NOW.replace(hour=18)) for _ in range(2)
    ]

    assert first_run[0] == first_run[1]
    assert second_run[0] == second_run[1]
