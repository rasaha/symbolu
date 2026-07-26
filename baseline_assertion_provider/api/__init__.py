"""Baseline assertion provider — public API surface."""
from __future__ import annotations

from ..version import __version__, CONTRACT_VERSION, TARGET_KERNEL_VERSION, TARGET_FRAMEWORK_VERSION
from ..provider import BaselineAssertionProvider, CAPABILITIES, MAPPING_VERSION, translate_error
from ..configuration import BaselineAssertionSettings, build_baseline_assertion_provider
from ..conformance import (
    BaselineAssertionConformanceReport, run_baseline_assertion_conformance)
from ..core import (
    BaselineAssertionEngine, BaselineAssertionOutcome, BaselineAssertionRequest,
    BaselineAssertionResult, BaselineEvidenceItem, BaselineRule)

__all__ = [
    "__version__", "CONTRACT_VERSION", "TARGET_KERNEL_VERSION", "TARGET_FRAMEWORK_VERSION",
    "BaselineAssertionProvider", "CAPABILITIES", "MAPPING_VERSION", "translate_error",
    "BaselineAssertionSettings", "build_baseline_assertion_provider",
    "BaselineAssertionConformanceReport", "run_baseline_assertion_conformance",
    "BaselineAssertionEngine", "BaselineAssertionOutcome", "BaselineAssertionRequest",
    "BaselineAssertionResult", "BaselineEvidenceItem", "BaselineRule",
]
