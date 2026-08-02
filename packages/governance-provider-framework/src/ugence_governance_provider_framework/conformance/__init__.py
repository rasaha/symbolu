"""Reusable provider conformance kits — one per provider kind.

The same kits will later certify TAP (assertion) and ActionGate (action) without
modification.
"""
from __future__ import annotations

from .common import CheckResult, ProviderConformanceReport
from .assertion import run_assertion_provider_conformance
from .action import run_action_provider_conformance
from .execution import run_execution_provider_conformance

__all__ = [
    "run_assertion_provider_conformance",
    "run_action_provider_conformance",
    "run_execution_provider_conformance",
    "ProviderConformanceReport",
    "CheckResult",
]
