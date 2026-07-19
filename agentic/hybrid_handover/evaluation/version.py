#!/usr/bin/env python3
"""Benchmark version + compatibility identifiers.

Frozen as part of the Version 1.0 benchmark. The version changes ONLY under the
rules in BENCHMARK_VERSIONING.md — never as a side effect of editing an extractor.
"""

from __future__ import annotations

BENCHMARK_NAME = "Sovereign Evidence Extraction Benchmark (SEEB)"
BENCHMARK_VERSION = "1.0.0"

# Bump MAJOR when case semantics or metric definitions change (breaks
# comparability with prior baselines). Bump MINOR for additive, backward-
# compatible cases/capabilities. Bump PATCH for documentation or objective
# ground-truth corrections that do not change any passing/failing outcome.
CASE_COUNT_V1 = 16
METRIC_SET_V1 = (
    "critical_evidence_recall",
    "defeater_recall",
    "definition_recall",
    "precedence_recall",
    "packet_sufficiency",
    "unsafe_handover_rate",
    "unsupported_claim_rate",
    "coverage_completeness",
    "routing_accuracy",
    "fail_closed_rate",
)
