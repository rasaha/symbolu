#!/usr/bin/env python3
"""
Hybrid Handover — enterprise-readiness evaluation framework.

A modular, extractor-agnostic falsification harness for the sovereign hybrid
handover layer. It answers one question: *can the sovereign layer reliably
produce complete evidence packets sufficient for downstream reasoning?* — and it
is built to falsify that claim, not confirm it.

The frozen handover package is imported, never modified. Any future extractor,
frontier model, or validator plugs in via ``protocols.py``.

Entry point: ``python -m agentic.hybrid_handover.evaluation.run_eval``.
"""

from .cases import EvalCase, PrecedenceReq, RequiredSpan
from .corpus import ALL_CASE_BUILDERS, CONTROL_CASE_IDS, all_cases
from .integrity import IntegrityReport, Issue, check_all, check_case
from .version import BENCHMARK_NAME, BENCHMARK_VERSION
from .harness import CaseResult, evaluate_case
from .injectors import ALL_INJECTORS, CORPUS_INJECTORS, PACKET_INJECTORS, Injector
from .metrics import Aggregate, Frac, precedence_recall, recall, unsupported_claims
from .protocols import ExtractorProtocol, FrontierProtocol, ValidatorProtocol
from .report import aggregate, build_report, classify, render_json, render_markdown
from .run_eval import run
from .validators import (
    DEFAULT_VALIDATORS,
    ContradictionSearchValidator,
    CoverageValidator,
    EvidenceToClaimValidator,
    SpanIntegrityValidator,
    ValidationOutcome,
)

__all__ = [
    "EvalCase", "RequiredSpan", "PrecedenceReq",
    "all_cases", "ALL_CASE_BUILDERS", "CONTROL_CASE_IDS",
    "evaluate_case", "CaseResult",
    "Injector", "ALL_INJECTORS", "PACKET_INJECTORS", "CORPUS_INJECTORS",
    "recall", "precedence_recall", "unsupported_claims", "Aggregate", "Frac",
    "ExtractorProtocol", "FrontierProtocol", "ValidatorProtocol",
    "SpanIntegrityValidator", "EvidenceToClaimValidator",
    "ContradictionSearchValidator", "CoverageValidator",
    "ValidationOutcome", "DEFAULT_VALIDATORS",
    "aggregate", "classify", "build_report", "render_markdown", "render_json",
    "run",
    "check_all", "check_case", "IntegrityReport", "Issue",
    "BENCHMARK_NAME", "BENCHMARK_VERSION",
]
