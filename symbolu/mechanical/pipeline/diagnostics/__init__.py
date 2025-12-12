"""
Symbol-U Pipeline Diagnostics
==============================

Diagnostic and evaluation tools for the Symbol-U pipeline.

Modules:
    - phonetic_stutter_eval: Empirical testing for phonetic stuttering hypothesis
    - phase_minus_one_metrics: Metrics and violation logging for Phase −1 grounding
"""

from .phonetic_stutter_eval import (
    PhoneticStutterEvaluator,
    PhonemeExtractor,
    BrokennessCalculator,
    PhoneticReranker,
    CorpusGenerator,
    run_hypothesis_test,
)

from .phase_minus_one_metrics import (
    PhaseMinusOneMetrics,
    PhaseMinusOneMetricsSnapshot,
    get_metrics,
    record_envelope,
    record_violation,
    get_metrics_snapshot,
    emit_metrics_log,
)

__all__ = [
    # Phonetic stutter evaluation
    "PhoneticStutterEvaluator",
    "PhonemeExtractor",
    "BrokennessCalculator",
    "PhoneticReranker",
    "CorpusGenerator",
    "run_hypothesis_test",
    # Phase −1 metrics
    "PhaseMinusOneMetrics",
    "PhaseMinusOneMetricsSnapshot",
    "get_metrics",
    "record_envelope",
    "record_violation",
    "get_metrics_snapshot",
    "emit_metrics_log",
]
