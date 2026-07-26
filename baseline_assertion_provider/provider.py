"""BaselineAssertionProvider — a capability-limited AssertionGovernanceProvider.

Adapts the baseline engine onto the neutral ``AssertionGovernanceProvider``
contract. Honestly declares a limited capability set (exact evidence matching,
contradiction detection, missing-evidence detection) and never claims the rich
capabilities TAP offers. Fail-safe: infrastructure failure → INDETERMINATE,
never SUPPORTED; no native exception crosses the boundary.

Independent of TAP and of every action provider (enforced by tests).
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from governance_providers.api import (
    AssertionCoverage, AssertionGovernanceRequest, AssertionGovernanceResult, BaseProvider,
    ProviderCapabilities, ProviderCompatibility, ProviderConfigurationError, ProviderDescriptor,
    ProviderError, ProviderHealth, ProviderKind, ProviderLifecycleState,
    ProviderResultValidationError, ProviderTimeoutError, ProviderUnavailableError)

from .core import (
    BaselineAssertionConfigError, BaselineAssertionEngine, BaselineAssertionError,
    BaselineAssertionMalformed, BaselineAssertionOutcome, BaselineAssertionRequest,
    BaselineAssertionTimeout, BaselineAssertionUnavailable, BaselineEvidenceItem)
from .version import __version__ as PROVIDER_VERSION

_CONTRACT_VERSION = "1.0.0"
MAPPING_VERSION = "baseline-assertion-map-1"

#: honestly-declared capabilities (a strict subset of TAP's)
CAPABILITIES = frozenset({
    "evaluate", "exact_evidence_matching", "contradiction_detection",
    "missing_evidence_detection", "in_process"})

_OUTCOME_MAP = {
    BaselineAssertionOutcome.SUPPORTED: AssertionCoverage.SUPPORTED,
    BaselineAssertionOutcome.UNSUPPORTED: AssertionCoverage.UNSUPPORTED,
    BaselineAssertionOutcome.INDETERMINATE: AssertionCoverage.INDETERMINATE,
    BaselineAssertionOutcome.UNKNOWN: AssertionCoverage.INDETERMINATE,
}
_ERROR_MAP = {
    BaselineAssertionConfigError: ProviderConfigurationError,
    BaselineAssertionTimeout: ProviderTimeoutError,
    BaselineAssertionMalformed: ProviderResultValidationError,
    BaselineAssertionUnavailable: ProviderUnavailableError,
}


def translate_error(exc: Exception) -> ProviderError:
    for native, provider in _ERROR_MAP.items():
        if isinstance(exc, native):
            return provider(f"baseline-assertion: {exc}")
    if isinstance(exc, BaselineAssertionError):
        return ProviderError(f"baseline-assertion: {exc}")
    return ProviderError(f"baseline-assertion-unexpected: {type(exc).__name__}: {exc}")


class BaselineAssertionProvider(BaseProvider):
    def __init__(self, engine: BaselineAssertionEngine, *,
                 provider_id: str = "baseline-assertion", default: bool = False,
                 fail_safe: bool = True) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=ProviderKind.ASSERTION_GOVERNANCE,
            implementation_version=PROVIDER_VERSION,
            compatibility=ProviderCompatibility(
                contract_version=_CONTRACT_VERSION, compatible_kernel_majors=frozenset({"1"}),
                config_schema_version="1"),
            capabilities=ProviderCapabilities(
                kind=ProviderKind.ASSERTION_GOVERNANCE, features=CAPABILITIES, deterministic=True),
            factory=lambda: BaselineAssertionProvider(engine, provider_id=provider_id,
                                                      default=default, fail_safe=fail_safe),
            vendor="BaselineAssertion", default=default,
            metadata={"mode": "in_process"})
        super().__init__(descriptor)
        self._engine = engine
        self._fail_safe = fail_safe

    def evaluate(self, request: AssertionGovernanceRequest) -> AssertionGovernanceResult:
        native = BaselineAssertionRequest(
            assertion=request.assertion,
            evidence=tuple(BaselineEvidenceItem(evidence_id=r, source_reference=r,
                                                provenance="caller_supplied")
                           for r in request.evidence_refs),
            context={str(k): v for k, v in dict(request.context).items()},
            correlation_id=request.correlation_id)
        try:
            result = self._engine.evaluate(native)
        except Exception as exc:  # translate — no native exception may escape
            err = translate_error(exc)
            if not self._fail_safe:
                raise err
            return self._indeterminate(f"provider_error:{type(err).__name__}",
                                       native.correlation_id)
        coverage = _OUTCOME_MAP.get(result.outcome, AssertionCoverage.INDETERMINATE)
        ratio = 1.0 if coverage is AssertionCoverage.SUPPORTED else 0.0
        fp = self._fingerprint(coverage, result.matched_evidence_ids, result.reason_codes,
                               result.trace_id)
        return AssertionGovernanceResult(
            coverage=coverage, evidence_coverage=ratio,
            covered_evidence_refs=result.matched_evidence_ids,
            explanation_refs=tuple(f"reason:{c}" for c in result.reason_codes),
            provider_trace_id=result.trace_id, fingerprint=fp)

    def _indeterminate(self, reason: str, trace: str) -> AssertionGovernanceResult:
        fp = self._fingerprint(AssertionCoverage.INDETERMINATE, (), (reason,), trace)
        return AssertionGovernanceResult(
            coverage=AssertionCoverage.INDETERMINATE, evidence_coverage=0.0,
            explanation_refs=(f"reason:{reason}",), provider_trace_id=trace, fingerprint=fp)

    @staticmethod
    def _fingerprint(coverage, matched, reasons, trace) -> str:
        payload = json.dumps({"c": coverage.value, "m": sorted(matched),
                              "r": sorted(reasons), "t": trace}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def health(self) -> ProviderHealth:
        base = super().health()
        ok = False
        try:
            ok = self._engine.available
        except Exception:  # noqa: BLE001
            ok = False
        state = base.state
        if base.healthy and not ok:
            state = ProviderLifecycleState.DEGRADED
        return ProviderHealth(state=state, healthy=base.healthy and ok,
                              detail=f"{base.detail}|policy:{self._engine.policy_version}")


assert issubclass(BaselineAssertionProvider, BaseProvider)
