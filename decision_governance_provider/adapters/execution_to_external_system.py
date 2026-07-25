"""Adapter: ExecutionProvider → kernel ExternalExecutionPort.

Implements the frozen ``ExternalExecutionPort`` (``dispatch`` + ``query_status``)
by delegating to an :class:`ExecutionProvider` and mapping its neutral
:class:`DispatchReceipt` / :class:`ObservationReport` onto the kernel transport /
status responses. A transport acknowledgement is never a business outcome — the
kernel invariant is preserved.
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

from ..contracts import ExecutionProvider


class ExecutionProviderExternalSystemAdapter:
    """Implements ``ExternalExecutionPort`` over an :class:`ExecutionProvider`."""

    def __init__(
        self,
        provider: ExecutionProvider,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._provider = provider
        self._new_id = id_factory
        self._clock = clock

    def dispatch(self, intent) -> ExternalDispatchResponse:
        receipt = self._provider.dispatch(
            action_type=intent.action_type,
            parameters=dict(getattr(intent, "authorized_parameters", {})))
        if not receipt.accepted:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TRANSPORT_FAILED,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="PROVIDER_REJECTED",
                error_detail=receipt.transport_error or "provider did not accept dispatch")
        ext_id = receipt.external_request_id or self._new_id("prov")
        if receipt.timed_out:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TIMED_OUT, external_request_id=ext_id,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="TIMEOUT", error_detail=receipt.transport_error or "provider timed out")
        return ExternalDispatchResponse(
            transport_status=TransportStatus.ACKNOWLEDGED, external_request_id=ext_id,
            acknowledgement=receipt.acknowledgement or f"ack:{ext_id}",
            retry_classification=RetryClassification.IDEMPOTENT_SAFE)

    def query_status(self, external_request_id: str) -> ExternalStatusResponse:
        report = self._provider.observe(external_request_id=external_request_id)
        return ExternalStatusResponse(
            external_request_id=external_request_id,
            business_outcome=KernelBusinessOutcome(report.business_outcome.value),
            observed_parameters=dict(report.observed_parameters),
            external_result_id=self._new_id("provres"),
            observed_at=self._clock(),
            finality=Finality.FINAL if report.final else Finality.UNKNOWN,
            reason_codes=(report.reason,) if report.reason else ())
