"""TAP provider — public API surface."""
from __future__ import annotations

from ..version import __version__, CONTRACT_VERSION, TARGET_KERNEL_VERSION, TARGET_FRAMEWORK_VERSION
from ..provider import TAPProvider
from ..configuration import TapSettings, build_tap_provider
from ..client import TapClient, InProcessTapClient, RemoteTapClient
from ..observability import TapInvocationLog, TapInvocationRecord
from ..health import TapHealthReport, check as check_health
from ..conformance import TapConformanceReport, run_tap_conformance
from ..errors import translate_error
from ..core import (
    TapConstraint, TapEngine, TapEvaluationRequest, TapEvaluationResult,
    TapEvidenceClass, TapEvidenceItem, TapObligation, TapOutcome, TapRule)
from ..mapping import (
    MAPPING_VERSION, KNOWN_CONSTRAINT_TYPES, KNOWN_OBLIGATION_TYPES,
    indeterminate_result, map_request, map_result)

__all__ = [
    "__version__", "CONTRACT_VERSION", "TARGET_KERNEL_VERSION", "TARGET_FRAMEWORK_VERSION",
    "TAPProvider", "TapSettings", "build_tap_provider",
    "TapClient", "InProcessTapClient", "RemoteTapClient",
    "TapInvocationLog", "TapInvocationRecord",
    "TapHealthReport", "check_health",
    "TapConformanceReport", "run_tap_conformance", "translate_error",
    "TapEngine", "TapEvaluationRequest", "TapEvaluationResult", "TapOutcome",
    "TapEvidenceItem", "TapEvidenceClass", "TapConstraint", "TapObligation", "TapRule",
    "MAPPING_VERSION", "KNOWN_CONSTRAINT_TYPES", "KNOWN_OBLIGATION_TYPES",
    "indeterminate_result", "map_request", "map_result",
]
