"""TAPProvider — a real AssertionGovernanceProvider on the DGM framework.

Wraps the TAP core (in-process or remote client) and implements the neutral
``AssertionGovernanceProvider`` contract by mapping requests/results and
translating errors. TAP governs **assertion support only** — whether an assertion
is supported, unsupported, constrained, or indeterminate relative to supplied
evidence. It has no authorize/dispatch/execute surface and never touches the
``ActionControlPlanePort`` or ``ExternalExecutionPort``.

Fail-safe policy (default ``fail_safe=True``): a native infrastructure failure is
translated to a classified framework error *and* converted to an INDETERMINATE
result, so the assertion assessment/recommendation workflow stays simple and can
never see a native exception or a promoted "supported". With ``fail_safe=False``
the classified ``ProviderError`` is raised for callers that normalize themselves.
Either way, no TAP-native exception crosses the boundary and infrastructure
failure never becomes SUPPORTED.
"""

from __future__ import annotations

from typing import Optional

from ugence_governance_provider_framework.api import (
    AssertionCoverage,
    AssertionGovernanceRequest,
    AssertionGovernanceResult,
    BaseProvider,
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderError,
    ProviderHealth,
    ProviderKind,
    ProviderLifecycleState,
)

from .client import TapClient
from .errors import translate_error
from .mapping import MAPPING_VERSION, indeterminate_result, map_request, map_result
from .observability import TapInvocationLog, TapInvocationRecord
from .version import __version__ as PROVIDER_VERSION

_CONTRACT_VERSION = "1.0.0"
_FEATURES = frozenset({
    "evaluate", "evidence_coverage", "component_analysis", "qualifier_analysis",
    "constraints", "obligations", "reason_codes", "in_process", "remote",
})


class TAPProvider(BaseProvider):
    """An AssertionGovernanceProvider backed by the TAP engine."""

    def __init__(self, client: TapClient, *, provider_id: str = "tap",
                 default: bool = True, fail_safe: bool = True,
                 evidence_resolution: str = "caller_supplied",
                 invocation_log: Optional[TapInvocationLog] = None) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=ProviderKind.ASSERTION_GOVERNANCE,
            implementation_version=PROVIDER_VERSION,
            compatibility=ProviderCompatibility(
                contract_version=_CONTRACT_VERSION, compatible_kernel_majors=frozenset({"1"}),
                config_schema_version="1"),
            capabilities=ProviderCapabilities(
                kind=ProviderKind.ASSERTION_GOVERNANCE, features=_FEATURES, deterministic=True),
            factory=lambda: TAPProvider(client, provider_id=provider_id, default=default,
                                        fail_safe=fail_safe,
                                        evidence_resolution=evidence_resolution),
            vendor="TAP", default=default,
            metadata={"mode": getattr(client, "mode", "in_process"),
                      "evidence_resolution": evidence_resolution})
        super().__init__(descriptor)
        self._client = client
        self._fail_safe = fail_safe
        self._evidence_resolution = evidence_resolution
        self._log = invocation_log

    # --- AssertionGovernanceProvider --------------------------------------

    def evaluate(self, request: AssertionGovernanceRequest) -> AssertionGovernanceResult:
        native = map_request(request, evidence_resolution=self._evidence_resolution)
        evidence_count = len(native.evidence)
        try:
            native_result = self._client.evaluate(native)
        except Exception as exc:  # translate — no native exception may escape
            provider_error = translate_error(exc)
            if not self._fail_safe:
                self._record(completed=False, evidence_count=evidence_count,
                             error=provider_error)
                raise provider_error
            # fail-safe: infrastructure failure → INDETERMINATE (never SUPPORTED)
            result = indeterminate_result(
                reason=f"provider_error:{type(provider_error).__name__}",
                trace_id=native.trace_id)
            self._record(completed=False, evidence_count=evidence_count, result=result,
                         error=provider_error)
            return result
        result = map_result(native_result)
        self._record(completed=True, evidence_count=evidence_count, result=result)
        return result

    # --- health & lifecycle -----------------------------------------------

    def health(self) -> ProviderHealth:
        base = super().health()
        engine_ok = False
        detail = base.detail
        try:
            engine_ok = self._client.ping()
            detail = f"{base.detail}|policy:{self._client.policy_version()}"
        except Exception:  # noqa: BLE001 - health must never raise
            engine_ok = False
        state = base.state
        if base.healthy and not engine_ok:
            state = ProviderLifecycleState.DEGRADED
        return ProviderHealth(state=state, healthy=base.healthy and engine_ok, detail=detail)

    # --- observability -----------------------------------------------------

    def _record(self, *, completed: bool, evidence_count: int,
                result: Optional[AssertionGovernanceResult] = None,
                error: Optional[ProviderError] = None) -> None:
        if self._log is None:
            return
        d = self.descriptor()
        outcome = result.coverage.value if result is not None else ""
        self._log.append(TapInvocationRecord(
            provider_id=d.provider_id, provider_version=d.implementation_version,
            mapping_version=MAPPING_VERSION, mode=d.metadata.get("mode", ""),
            compatible="1" in d.compatibility.compatible_kernel_majors,
            completed=completed, outcome=outcome,
            trace_id=result.provider_trace_id if result else "",
            policy_version=_safe_policy_version(self._client),
            evidence_count=evidence_count,
            evidence_coverage=result.evidence_coverage if result else None,
            fingerprint=result.fingerprint if result else "",
            error_class=type(error).__name__ if error else None,
            failure_class=getattr(error, "failure_class", None).value if error else None))


def _safe_policy_version(client: TapClient) -> str:
    try:
        return client.policy_version()
    except Exception:  # noqa: BLE001
        return ""


# structural self-check: a TAPProvider is a framework provider
assert issubclass(TAPProvider, BaseProvider)
assert AssertionCoverage  # imported for downstream typing / re-export symmetry
