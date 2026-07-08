"""One-shot scaffold for Phase 1 folder structure and stub files."""
from __future__ import annotations

import pathlib

BASE = pathlib.Path(__file__).parent.parent

# ── directories ──────────────────────────────────────────────────────────────
dirs = [
    "config",
    "scripts",
    "vera",
    "vera/api",
    "vera/api/endpoints",
    "vera/api/models",
    "vera/contexts",
    "vera/store",
    "vera/features",
    "vera/signals",
    "vera/signals/yaml",
    "vera/goals",
    "vera/goals/yaml",
    "vera/candidates",
    "vera/ranking",
    "vera/engine",
    "vera/tracing",
    "vera/metrics",
    "vera/validation",
    "vera/fallback",
    "vera/strategies",
    "vera/categories",
    "vera/templates",
    "vera/templates/yaml",
    "vera/templates/yaml/dentists",
    "vera/templates/yaml/salons",
    "vera/templates/yaml/restaurants",
    "vera/templates/yaml/gyms",
    "vera/templates/yaml/pharmacies",
    "vera/templates/yaml/shared",
    "vera/templates/yaml/fallbacks",
    "vera/rules",
    "vera/rules/yaml",
    "vera/scoring",
    "vera/conversation",
    "vera/dataset",
    "vera/submission",
    "vera/utils",
    "vera/optimization",
    "tests",
    "tests/unit",
    "tests/integration",
    "tests/category",
    "tests/judge",
]
for d in dirs:
    (BASE / d).mkdir(parents=True, exist_ok=True)

# ── __init__.py stubs ─────────────────────────────────────────────────────────
pkg_inits = {
    "vera": "Vera — deterministic message composition engine.",
    "vera/api": "HTTP API layer.",
    "vera/api/endpoints": "FastAPI endpoint handlers.",
    "vera/api/models": "Pydantic request/response models.",
    "vera/contexts": "Pydantic schemas for the four context objects.",
    "vera/store": "Context persistence layer (Redis + in-memory fallback).",
    "vera/features": "Layer 1 — Feature Extraction. Implemented in Phase 3.",
    "vera/signals": "Layer 2 — Signal Detection. Implemented in Phase 3.",
    "vera/goals": "Layer 3 — Business Goal Inference. Implemented in Phase 4.",
    "vera/candidates": "Layer 4 — Candidate Action Generation. Implemented in Phase 5.",
    "vera/ranking": "Layers 5-6 — Template Ranking + Weighted Scoring. Implemented in Phase 6.",
    "vera/engine": "Core composition orchestrator.",
    "vera/tracing": "Decision Trace — internal debug artifacts, never returned by API.",
    "vera/metrics": "Pipeline performance metrics, logged at DEBUG level only.",
    "vera/validation": "Startup validation framework.",
    "vera/fallback": "Safe fallback chain. Implemented in Phase 7.",
    "vera/strategies": "Per-trigger-kind slot builders. Implemented in Phase 8.",
    "vera/categories": "Per-category voice + strategy rules. Implemented in Phase 8.",
    "vera/templates": "Template system (Jinja2 + YAML). Implemented in Phase 6.",
    "vera/rules": "Declarative rule engine. Implemented in Phase 2.",
    "vera/scoring": "Post-compose self-validation gate. Implemented in Phase 8.",
    "vera/conversation": "Multi-turn conversation logic. Implemented in Phase 5.",
    "vera/dataset": "Dataset loader for local testing and optimize.py.",
    "vera/submission": "Challenge submission artifacts.",
    "vera/utils": "Shared utilities.",
    "vera/optimization": "Weight tuning utilities for optimize.py.",
    "tests": "Test suite.",
    "tests/unit": "Unit tests.",
    "tests/integration": "Integration tests.",
    "tests/category": "Category-specific strategy tests.",
    "tests/judge": "Judge-harness compatibility tests.",
}
for rel, doc in pkg_inits.items():
    p = BASE / rel / "__init__.py"
    if not p.exists():
        p.write_text(f'"""{doc}"""\n', encoding="utf-8")


def write_stub(path: str, content: str) -> None:
    p = BASE / path
    if not p.exists():
        p.write_text(content, encoding="utf-8")


# ── strategy stubs ────────────────────────────────────────────────────────────
strategy_stubs = [
    ("research_digest", "ResearchDigestStrategy", "research_digest, cde_opportunity"),
    ("performance", "PerformanceStrategy", "perf_spike, perf_dip, seasonal_perf_dip"),
    ("planning_intent", "PlanningIntentStrategy", "active_planning_intent"),
    ("festival", "FestivalStrategy", "festival_upcoming, ipl_match_today, category_seasonal"),
    ("compliance", "ComplianceStrategy", "regulation_change, supply_alert"),
    ("competitor", "CompetitorStrategy", "competitor_opened"),
    ("milestone", "MilestoneStrategy", "milestone_reached"),
    ("dormancy", "DormancyStrategy", "dormant_with_vera, winback_eligible"),
    ("renewal", "RenewalStrategy", "renewal_due"),
    ("recall", "RecallStrategy", "recall_due"),
    ("lapse", "LapseStrategy", "customer_lapsed_soft, customer_lapsed_hard"),
    ("refill", "RefillStrategy", "chronic_refill_due"),
    ("trial_followup", "TrialFollowupStrategy", "trial_followup"),
    ("curious_ask", "CuriousAskStrategy", "curious_ask_due"),
    ("gbp_verification", "GbpVerificationStrategy", "gbp_unverified"),
]
for module, cls, kinds in strategy_stubs:
    write_stub(
        f"vera/strategies/{module}.py",
        f'"""Slot builder for {kinds} triggers. Implemented in Phase 8."""\nfrom __future__ import annotations\n\nfrom vera.strategies.base_strategy import BaseStrategy\n\n\nclass {cls}(BaseStrategy):\n    """Phase 8: Not yet implemented."""\n',
    )

# ── category stubs ────────────────────────────────────────────────────────────
categories = [
    ("dentists", "DentistsCategoryStrategy"),
    ("salons", "SalonsCategoryStrategy"),
    ("restaurants", "RestaurantsCategoryStrategy"),
    ("gyms", "GymsCategoryStrategy"),
    ("pharmacies", "PharmaciesCategoryStrategy"),
]
for slug, cls in categories:
    write_stub(
        f"vera/categories/{slug}.py",
        f'"""Category strategy for {slug}. Implemented in Phase 8."""\nfrom __future__ import annotations\n\nfrom vera.categories.base_category import BaseCategoryStrategy\n\n\nclass {cls}(BaseCategoryStrategy):\n    """Phase 8: Not yet implemented."""\n\n    category_slug: str = "{slug}"\n',
    )

# ── misc stubs ────────────────────────────────────────────────────────────────
misc_stubs = {
    "vera/rules/suppression_rules.py": "Suppression rule helpers. Implemented in Phase 2.",
    "vera/rules/cta_rules.py": "CTA selection rule helpers. Implemented in Phase 2.",
    "vera/rules/send_as_rules.py": "Send-as selection rule helpers. Implemented in Phase 2.",
    "vera/rules/language_rules.py": "Language selection rule helpers. Implemented in Phase 2.",
    "vera/rules/rule_engine.py": "Declarative YAML rule evaluator. Implemented in Phase 2.",
    "vera/scoring/output_validator.py": "Post-compose schema validator. Implemented in Phase 8.",
    "vera/scoring/anti_patterns.py": "Anti-pattern detector. Implemented in Phase 8.",
    "vera/scoring/compulsion_checker.py": "Compulsion lever checker. Implemented in Phase 8.",
    "vera/conversation/state_machine.py": "Conversation state machine. Implemented in Phase 5.",
    "vera/conversation/auto_reply_detector.py": "WA auto-reply detector. Implemented in Phase 5.",
    "vera/conversation/intent_classifier.py": "Intent classifier. Implemented in Phase 5.",
    "vera/conversation/reply_composer.py": "Reply composer. Implemented in Phase 5.",
    "vera/dataset/loader.py": "Dataset loader. Implemented in Phase 9.",
    "vera/dataset/generator.py": "Dataset generator wrapper. Implemented in Phase 9.",
    "vera/submission/bot.py": "Submission bot.py wrapper. Implemented in Phase 9.",
    "vera/submission/conversation_handlers.py": "Conversation handlers for submission. Implemented in Phase 9.",
    "vera/submission/submission_runner.py": "Submission runner — generates submission.jsonl. Implemented in Phase 9.",
    "vera/optimization/heuristic_scorer.py": "Fast heuristic scorer for optimize.py. Implemented in Phase 9.",
    "vera/optimization/weight_tuner.py": "Weight tuner for optimize.py. Implemented in Phase 9.",
    "vera/optimization/results_formatter.py": "Results formatter for optimize.py. Implemented in Phase 9.",
    "vera/templates/template_engine.py": "Jinja2 slot-filler. Implemented in Phase 6.",
    "vera/templates/template_registry.py": "Template registry and index. Implemented in Phase 6.",
    "vera/ranking/template_ranker.py": "Template ranker. Implemented in Phase 6.",
    "vera/ranking/candidate_ranker.py": "Candidate ranker — picks winner. Implemented in Phase 6.",
    "vera/ranking/weighted_scorer.py": "Weighted scorer using config/weights.yaml. Implemented in Phase 6.",
    "vera/fallback/fallback_chain.py": "Three-level fallback chain. Implemented in Phase 7.",
    "vera/engine/suppression.py": "Suppression key dedup. Implemented in Phase 2.",
    "vera/engine/anti_repetition.py": "Body-hash dedup per conversation. Implemented in Phase 2.",
    "vera/engine/conversation_manager.py": "Turn tracking and conversation state. Implemented in Phase 5.",
    "vera/tracing/trace_builder.py": "Assembles DecisionTrace from PipelineContext. Implemented in Phase 4.",
    "vera/features/extractor.py": "FeatureExtractor orchestrator. Implemented in Phase 3.",
    "vera/features/merchant_features.py": "Merchant context feature extraction. Implemented in Phase 3.",
    "vera/features/category_features.py": "Category context feature extraction. Implemented in Phase 3.",
    "vera/features/customer_features.py": "Customer context feature extraction. Implemented in Phase 3.",
    "vera/features/trigger_features.py": "Trigger context feature extraction. Implemented in Phase 3.",
    "vera/signals/signal_detector.py": "Evaluates FeatureSet against signal rules. Implemented in Phase 3.",
    "vera/goals/goal_inferrer.py": "Infers GoalContext from FeatureSet + SignalSet. Implemented in Phase 4.",
    "vera/candidates/candidate_generator.py": "Generates N candidates per trigger. Implemented in Phase 5.",
    "vera/cli.py": "CLI entry point (python -m vera.cli). Implemented in Phase 9.",
    "vera/utils/time_utils.py": "Time utilities and expiry helpers. Implemented in Phase 2.",
    "vera/utils/text_utils.py": "Text utilities (language detection, truncation). Implemented in Phase 2.",
    "vera/utils/json_utils.py": "Safe JSON parse/serialize helpers. Implemented in Phase 2.",
}
for path, note in misc_stubs.items():
    write_stub(path, f'"""\n{note}\n"""\nfrom __future__ import annotations\n\n__all__: list[str] = []\n')

# ── test stubs ────────────────────────────────────────────────────────────────
test_stubs = {
    "tests/unit/test_context_models.py": "Context model schema validation tests.",
    "tests/unit/test_store.py": "Store CRUD, TTL, and version conflict tests.",
    "tests/unit/test_suppression.py": "Suppression key logic tests.",
    "tests/unit/test_feature_extractor.py": "Feature extractor unit tests.",
    "tests/unit/test_signal_detector.py": "Signal detector unit tests.",
    "tests/unit/test_goal_inferrer.py": "Goal inferrer unit tests.",
    "tests/unit/test_candidate_generator.py": "Candidate generator unit tests.",
    "tests/unit/test_template_ranker.py": "Template ranker unit tests.",
    "tests/unit/test_weighted_scorer.py": "Weighted scorer unit tests.",
    "tests/unit/test_decision_trace.py": "DecisionTrace population tests.",
    "tests/unit/test_pipeline_context.py": "PipelineContext compute-once tests.",
    "tests/unit/test_startup_validator.py": "Startup validator pass/fail tests.",
    "tests/unit/test_pipeline_timer.py": "PipelineTimer precision tests.",
    "tests/unit/test_fallback_chain.py": "FallbackChain L1/L2/L3 tests.",
    "tests/unit/test_auto_reply_detector.py": "WA auto-reply pattern tests.",
    "tests/unit/test_intent_classifier.py": "Intent classification tests.",
    "tests/unit/test_cta_rules.py": "CTA rule selection tests.",
    "tests/unit/test_language_rules.py": "Language rule tests.",
    "tests/unit/test_anti_patterns.py": "Anti-pattern detection tests.",
    "tests/unit/test_template_engine.py": "Template slot-fill tests.",
    "tests/integration/test_api_healthz.py": "GET /v1/healthz contract tests.",
    "tests/integration/test_api_context.py": "POST /v1/context idempotency tests.",
    "tests/integration/test_api_tick.py": "POST /v1/tick response tests.",
    "tests/integration/test_api_reply.py": "POST /v1/reply state machine tests.",
    "tests/integration/test_full_conversation.py": "End-to-end 5-turn conversation tests.",
    "tests/integration/test_full_pipeline_determinism.py": "Same inputs x3 = same output tests.",
    "tests/category/test_dentist_strategy.py": "Dentist trigger x voice tests.",
    "tests/category/test_salon_strategy.py": "Salon trigger x voice tests.",
    "tests/category/test_restaurant_strategy.py": "Restaurant trigger x voice tests.",
    "tests/category/test_gym_strategy.py": "Gym trigger x voice tests.",
    "tests/category/test_pharmacy_strategy.py": "Pharmacy trigger x voice tests.",
    "tests/judge/test_case_studies.py": "Case study composition quality tests.",
    "tests/judge/test_submission.py": "30-pair submission validation tests.",
}
for path, note in test_stubs.items():
    write_stub(
        path,
        f'"""\n{note}\nImplemented alongside the phases they test.\n"""\nfrom __future__ import annotations\n\n# Tests will be added in the corresponding phase.\n',
    )

# ── script stubs ──────────────────────────────────────────────────────────────
for name, note in [
    ("load_dataset", "Warm the store with all seed data. Phase 9."),
    ("run_submission", "Generate submission.jsonl locally. Phase 9."),
    ("benchmark_latency", "Measure /v1/tick latency under load. Phase 9."),
]:
    write_stub(
        f"scripts/{name}.py",
        f'"""Script: {note}"""\nfrom __future__ import annotations\n\nif __name__ == "__main__":\n    raise NotImplementedError("Phase 9")\n',
    )

# ── YAML scaffolds ────────────────────────────────────────────────────────────
yaml_stubs = {
    "vera/signals/yaml/signal_definitions.yaml": (
        "# Signal definitions — see §4.5 of implementation roadmap.\n"
        "# Implemented in Phase 3.\nsignals: []\n"
    ),
    "vera/goals/yaml/goal_definitions.yaml": (
        "# Goal inference rules — see §4.6 of implementation roadmap.\n"
        "# Implemented in Phase 4.\ngoals: []\n"
    ),
    "vera/rules/yaml/suppression_rules.yaml": (
        "# Suppression rules — Implemented in Phase 2.\nrules: []\n"
    ),
    "vera/rules/yaml/cta_rules.yaml": (
        "# CTA selection rules — Implemented in Phase 2.\nrules: []\n"
    ),
    "vera/rules/yaml/urgency_priority.yaml": (
        "# Urgency priority rules — Implemented in Phase 2.\nrules: []\n"
    ),
    "vera/templates/yaml/fallbacks/category_fallbacks.yaml": (
        "# Level-1 category generic fallback templates — Implemented in Phase 7.\n"
        "fallback_templates: []\n"
    ),
    "vera/templates/yaml/fallbacks/shared_fallbacks.yaml": (
        "# Level-2 shared generic fallback templates — Implemented in Phase 7.\n"
        "fallback_templates: []\n"
    ),
}
for path, content in yaml_stubs.items():
    p = BASE / path
    if not p.exists():
        p.write_text(content, encoding="utf-8")

# ── optimize.py root stub ──────────────────────────────────────────────────────
write_stub(
    "optimize.py",
    '"""\noptimize.py — Weight tuning CLI.\nRuns full heuristic pipeline on canonical dataset.\nImplemented in Phase 9.\n\nUsage:\n    python optimize.py [--category] [--trigger-kind] [--set key=value]\n                       [--compare file1 file2] [--output file] [--top-n N]\n                       [--submission-pairs]\n"""\nfrom __future__ import annotations\n\nif __name__ == "__main__":\n    raise NotImplementedError("Phase 9")\n',
)

print("=" * 60)
print("Phase 1 scaffold complete.")
print(f"Base directory : {BASE}")
print(f"Directories    : {len(dirs)}")
print(f"Strategy stubs : {len(strategy_stubs)}")
print(f"Category stubs : {len(categories)}")
print(f"Test stubs     : {len(test_stubs)}")
print(f"Misc stubs     : {len(misc_stubs)}")
print("=" * 60)
