"""Baseline action provider — public API surface."""
from __future__ import annotations

from ..version import __version__, CONTRACT_VERSION, TARGET_KERNEL_VERSION, TARGET_FRAMEWORK_VERSION
from ..provider import BaselineActionProvider, CAPABILITIES, MAPPING_VERSION, translate_error
from ..configuration import BaselineActionSettings, build_baseline_action_provider
from ..conformance import BaselineActionConformanceReport, run_baseline_action_conformance
from ..core import (
    BaselineActionConstraint, BaselineActionDecision, BaselineActionEngine,
    BaselineActionObligation, BaselineActionOutcome, BaselineActionRequest, ConstrainedRule)

__all__ = [
    "__version__", "CONTRACT_VERSION", "TARGET_KERNEL_VERSION", "TARGET_FRAMEWORK_VERSION",
    "BaselineActionProvider", "CAPABILITIES", "MAPPING_VERSION", "translate_error",
    "BaselineActionSettings", "build_baseline_action_provider",
    "BaselineActionConformanceReport", "run_baseline_action_conformance",
    "BaselineActionEngine", "BaselineActionOutcome", "BaselineActionRequest",
    "BaselineActionDecision", "BaselineActionConstraint", "BaselineActionObligation",
    "ConstrainedRule",
]
