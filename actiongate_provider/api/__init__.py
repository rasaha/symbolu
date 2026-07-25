"""ActionGate provider — public API surface."""
from __future__ import annotations

from ..version import __version__, CONTRACT_VERSION, TARGET_KERNEL_VERSION, TARGET_FRAMEWORK_VERSION
from ..provider import ActionGateProvider
from ..configuration import ActionGateSettings, build_actiongate_provider
from ..client import ActionGateClient, InProcessActionGateClient, RemoteActionGateClient
from ..observability import ActionGateInvocationLog, ActionGateInvocationRecord
from ..health import ActionGateHealthReport, check as check_health
from ..conformance import ActionGateConformanceReport, run_actiongate_conformance
from ..core import (
    ActionGateConstraint, ActionGateDecision, ActionGateEngine, ActionGateObligation,
    ActionGateOutcome, ActionGateRequest, ConstrainedRule)
from ..mapping import MAPPING_VERSION, KNOWN_CONSTRAINT_TYPES, KNOWN_OBLIGATION_TYPES

__all__ = [
    "__version__", "CONTRACT_VERSION", "TARGET_KERNEL_VERSION", "TARGET_FRAMEWORK_VERSION",
    "ActionGateProvider", "ActionGateSettings", "build_actiongate_provider",
    "ActionGateClient", "InProcessActionGateClient", "RemoteActionGateClient",
    "ActionGateInvocationLog", "ActionGateInvocationRecord",
    "ActionGateHealthReport", "check_health",
    "ActionGateConformanceReport", "run_actiongate_conformance",
    "ActionGateEngine", "ActionGateRequest", "ActionGateDecision", "ActionGateOutcome",
    "ActionGateConstraint", "ActionGateObligation", "ConstrainedRule",
    "MAPPING_VERSION", "KNOWN_CONSTRAINT_TYPES", "KNOWN_OBLIGATION_TYPES",
]
