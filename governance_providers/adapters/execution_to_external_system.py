"""Adapter: ExternalExecutionProvider → kernel ExternalExecutionPort.

Preserves the transport/business-outcome split. Provider failures are normalized:
a dispatch failure becomes a transport failure; an observation failure becomes an
UNKNOWN business outcome. No vendor exception leaks into the kernel.
"""

from __future__ import annotations

from decision_governance.api.common import Clock, IdFactory, new_id, utc_now
from decision_governance.api.contracts import (
    BusinessOutcome as KernelBusinessOutcome,
    Finality,
    RetryClassification,
    TransportStatus,
)
from decision_governance.api.ports import ExternalDispatchResponse, ExternalStatusResponse

from ..contracts import ExecutionDispatchRequest
from ..contracts.execution import ExecutionBusinessOutcome, ExternalExecutionProvider
from ..errors import ProviderError

_OUTCOME_MAP = {
    ExecutionBusinessOutcome.SUCCEEDED: KernelBusinessOutcome.SUCCEEDED,
    ExecutionBusinessOutcome.FAILED: KernelBusinessOutcome.FAILED,
    ExecutionBusinessOutcome.REJECTED: KernelBusinessOutcome.REJECTED,
    ExecutionBusinessOutcome.PENDING: KernelBusinessOutcome.UNKNOWN,
    ExecutionBusinessOutcome.DUPLICATE: KernelBusinessOutcome.DUPLICATE,
    ExecutionBusinessOutcome.UNKNOWN: KernelBusinessOutcome.UNKNOWN,
}


class ExternalExecutionAdapter:
    """Implements ``ExternalExecutionPort`` over an :class:`ExternalExecutionProvider`."""

    def __init__(self, provider: ExternalExecutionProvider, *,
                 id_factory: IdFactory = new_id, clock: Clock = utc_now) -> None:
        self._provider = provider
        self._new_id = id_factory
        self._clock = clock

    def dispatch(self, intent) -> ExternalDispatchResponse:
        req = ExecutionDispatchRequest(
            action_type=intent.action_type,
            parameters=dict(getattr(intent, "authorized_parameters", {})),
            idempotency_key=getattr(intent, "execution_idempotency_key", ""),
            correlation_id=getattr(intent, "correlation_id", ""))
        try:
            r = self._provider.dispatch(req)
        except ProviderError as exc:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TRANSPORT_FAILED,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code=f"provider_error:{type(exc).__name__}", error_detail=str(exc))
        if not r.accepted:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TRANSPORT_FAILED,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="PROVIDER_REJECTED", error_detail=r.transport_error)
        ext_id = r.external_request_id or self._new_id("prov")
        if r.timed_out:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TIMED_OUT, external_request_id=ext_id,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="TIMEOUT", error_detail=r.transport_error)
        return ExternalDispatchResponse(
            transport_status=TransportStatus.ACKNOWLEDGED, external_request_id=ext_id,
            acknowledgement=r.acknowledgement or f"ack:{ext_id}",
            retry_classification=RetryClassification.IDEMPOTENT_SAFE)

    def query_status(self, external_request_id: str) -> ExternalStatusResponse:
        try:
            obs = self._provider.observe(external_request_id=external_request_id)
            outcome = _OUTCOME_MAP[obs.business_outcome]
            observed = dict(obs.observed_parameters)
            final = obs.final
            reasons = (obs.reason,) if obs.reason else ()
        except ProviderError as exc:
            outcome, observed, final = KernelBusinessOutcome.UNKNOWN, {}, False
            reasons = (f"provider_error:{type(exc).__name__}",)
        return ExternalStatusResponse(
            external_request_id=external_request_id, business_outcome=outcome,
            observed_parameters=observed, external_result_id=self._new_id("provres"),
            observed_at=self._clock(),
            finality=Finality.FINAL if final else Finality.UNKNOWN,
            reason_codes=reasons)
