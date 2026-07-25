"""Deterministic supplier adapter implementing the kernel ``ExternalExecutionPort``.

The supplier is the external system the governance execution phase dispatches to.
This adapter is fully deterministic (rule-based, no randomness, no network) and
speaks the kernel port directly: ``dispatch`` attempts the action and returns a
*transport* result; ``query_status`` returns an *observed business outcome*. A
transport acknowledgement is never a business outcome — exactly as the kernel
requires.

It is the procurement analogue of the hiring/offline execution adapter, proving
the same ``ExternalExecutionPort`` seam serves a different external system.
"""

from __future__ import annotations

from typing import Optional

from decision_governance.api.common import Clock, IdFactory, new_id, utc_now
from decision_governance.api.contracts import Finality, RetryClassification, TransportStatus
from decision_governance.api.ports import ExternalDispatchResponse, ExternalStatusResponse

from .outcomes import SupplierOutcome, business_outcome_for


class SupplierExecutionAdapter:
    """A deterministic supplier system behind the neutral execution port.

    Dispatch rules (in order, no randomness):

    * ``action_type`` in ``transport_failing`` → ``TRANSPORT_FAILED`` (no ack);
    * ``action_type`` in ``timing_out`` → ``TIMED_OUT`` (outcome unknown);
    * otherwise → ``ACKNOWLEDGED`` with a deterministic external request id.

    ``query_status`` returns the configured :class:`SupplierOutcome` for the
    action type (default ``ACCEPTED``), echoing the intent's authorized
    parameters back as the observed parameters.
    """

    def __init__(
        self,
        *,
        adapter_id: str = "offline-supplier",
        adapter_version: str = "1.0",
        outcomes: Optional[dict[str, SupplierOutcome]] = None,
        observed_parameter_overrides: Optional[dict[str, dict[str, str]]] = None,
        transport_failing: frozenset[str] = frozenset(),
        timing_out: frozenset[str] = frozenset(),
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self.adapter_id = adapter_id
        self.adapter_version = adapter_version
        self._outcomes = outcomes or {}
        self._observed_overrides = observed_parameter_overrides or {}
        self._transport_failing = transport_failing
        self._timing_out = timing_out
        self._new_id = id_factory
        self._clock = clock
        self._dispatched: dict[str, object] = {}

    def dispatch(self, intent) -> ExternalDispatchResponse:
        action_type = intent.action_type
        if action_type in self._transport_failing:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TRANSPORT_FAILED,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="SUPPLIER_UNREACHABLE",
                error_detail="offline supplier: transport down")
        ext_id = self._new_id("supreq")
        self._dispatched[ext_id] = intent
        if action_type in self._timing_out:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TIMED_OUT, external_request_id=ext_id,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="TIMEOUT", error_detail="offline supplier: no ack in window")
        return ExternalDispatchResponse(
            transport_status=TransportStatus.ACKNOWLEDGED, external_request_id=ext_id,
            acknowledgement=f"supplier-ack:{ext_id}",
            retry_classification=RetryClassification.IDEMPOTENT_SAFE)

    def query_status(self, external_request_id: str) -> ExternalStatusResponse:
        intent = self._dispatched.get(external_request_id)
        action_type = getattr(intent, "action_type", "")
        supplier_outcome = self._outcomes.get(action_type, SupplierOutcome.ACCEPTED)
        finality = (Finality.UNKNOWN
                    if supplier_outcome in (SupplierOutcome.TIMED_OUT, SupplierOutcome.UNKNOWN)
                    else Finality.FINAL)
        observed = self._observed_overrides.get(
            action_type,
            dict(getattr(intent, "authorized_parameters", {})) if intent else {})
        return ExternalStatusResponse(
            external_request_id=external_request_id,
            business_outcome=business_outcome_for(supplier_outcome),
            observed_parameters=observed,
            external_result_id=self._new_id("supres"),
            observed_at=self._clock(),
            finality=finality,
            reason_codes=(supplier_outcome.value,))
