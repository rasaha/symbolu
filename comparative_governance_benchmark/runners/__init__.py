"""Benchmark runners (provider-free): determinism, enforcement, obligations, DGM, execution.

This package intentionally exports only provider-free helpers so that a restricted
strategy module importing ``comparative_governance_benchmark.runners`` never pulls
a provider into its import graph. Provider-specific engine builders live under
``strategies/_*_support.py`` instead.
"""
from __future__ import annotations

from .common import (
    ActionFlow, CaseFlow, POSTURE, PROCEED, run_action_flow, run_case_flow, technical_valid)
from .dgm import DGMServices, build_services
from .enforcement import EnforcementResult, enforce
from .execution import DirectExecution, build_execution_adapter, direct_dispatch
from .obligations import ObligationRecord, compliance_verdict, verify_obligations

__all__ = [
    "build_services", "DGMServices", "run_case_flow", "run_action_flow", "CaseFlow",
    "ActionFlow", "technical_valid", "POSTURE", "PROCEED",
    "enforce", "EnforcementResult", "verify_obligations", "compliance_verdict",
    "ObligationRecord", "build_execution_adapter", "direct_dispatch", "DirectExecution",
]
