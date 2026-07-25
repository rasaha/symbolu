"""Provider-neutral external-system port + an offline deterministic adapter.

The domain depends only on :class:`ExternalExecutionPort` — never on a concrete
ATS/ERP/payment/ActionGate SDK. The port has two seams: ``dispatch`` (attempt the
action) and ``query_status`` (observe what actually happened). A transport
acknowledgement from ``dispatch`` is **not** a business outcome; business outcomes
come only from an observed ``query_status`` (or an external callback).

The offline adapter is fully deterministic (rule-based, no randomness, no network)
so the whole suite runs without external services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from pydantic import Field, model_validator

from ..common import Clock, IdFactory, new_id, utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .status import BusinessOutcome, Finality, RetryClassification, TransportStatus


class ExternalDispatchResponse(DomainModel):
    """The *transport* result of dispatching an intent. Not a business outcome."""

    transport_status: TransportStatus
    external_request_id: str = ""
    acknowledgement: str = ""
    retry_classification: RetryClassification = RetryClassification.NOT_RETRYABLE
    error_code: str = ""
    error_detail: str = ""


class ExternalStatusResponse(DomainModel):
    """An *observed* business outcome from the external system."""

    external_request_id: str
    business_outcome: BusinessOutcome
    observed_parameters: dict[str, str] = Field(default_factory=dict)
    external_result_id: str = ""
    observed_at: datetime = Field(default_factory=utc_now)
    finality: Finality = Finality.UNKNOWN
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "ExternalStatusResponse":
        if not self.external_request_id.strip():
            raise DomainValidationError("external_request_id is required")
        return self


@runtime_checkable
class ExternalExecutionPort(Protocol):
    """The single seam between governance and an external business system."""

    def dispatch(self, intent: "object") -> ExternalDispatchResponse: ...
    def query_status(self, external_request_id: str) -> ExternalStatusResponse: ...


class OfflineDeterministicExecutionAdapter:
    """A deterministic, offline external-system adapter for tests and development.

    Dispatch rules (evaluated in order, no randomness):

    * ``action_type`` in ``transport_failing`` → ``TRANSPORT_FAILED`` (no ack);
    * ``action_type`` in ``timing_out`` → ``TIMED_OUT`` (outcome unknown);
    * otherwise → ``ACKNOWLEDGED`` with a deterministic external request id.

    ``query_status`` returns the configured business outcome for the action type,
    defaulting to ``SUCCEEDED`` with the intent's authorized parameters echoed back.
    Neither call ever executes anything for real.
    """

    def __init__(
        self,
        *,
        adapter_id: str = "offline-exec",
        adapter_version: str = "1.0",
        transport_failing: frozenset[str] = frozenset(),
        timing_out: frozenset[str] = frozenset(),
        outcomes: Optional[dict[str, BusinessOutcome]] = None,
        observed_parameter_overrides: Optional[dict[str, dict[str, str]]] = None,
        finality: Finality = Finality.FINAL,
        retry_classification: RetryClassification = RetryClassification.IDEMPOTENT_SAFE,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self.adapter_id = adapter_id
        self.adapter_version = adapter_version
        self._transport_failing = transport_failing
        self._timing_out = timing_out
        self._outcomes = outcomes or {}
        self._observed_overrides = observed_parameter_overrides or {}
        self._finality = finality
        self._retry = retry_classification
        self._new_id = id_factory
        self._clock = clock
        self._dispatched: dict[str, object] = {}  # external_request_id -> intent

    def dispatch(self, intent) -> ExternalDispatchResponse:
        action_type = intent.action_type
        if action_type in self._transport_failing:
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TRANSPORT_FAILED,
                retry_classification=RetryClassification.IDEMPOTENT_SAFE,
                error_code="TRANSPORT_FAILED", error_detail="offline: transport down")
        ext_id = self._new_id("ext")
        if action_type in self._timing_out:
            self._dispatched[ext_id] = intent
            return ExternalDispatchResponse(
                transport_status=TransportStatus.TIMED_OUT, external_request_id=ext_id,
                retry_classification=self._retry,
                error_code="TIMEOUT", error_detail="offline: no ack within window")
        self._dispatched[ext_id] = intent
        return ExternalDispatchResponse(
            transport_status=TransportStatus.ACKNOWLEDGED, external_request_id=ext_id,
            acknowledgement=f"ack:{ext_id}", retry_classification=self._retry)

    def query_status(self, external_request_id: str) -> ExternalStatusResponse:
        intent = self._dispatched.get(external_request_id)
        action_type = getattr(intent, "action_type", "")
        outcome = self._outcomes.get(action_type, BusinessOutcome.SUCCEEDED)
        observed = self._observed_overrides.get(
            action_type,
            dict(getattr(intent, "authorized_parameters", {})) if intent else {})
        return ExternalStatusResponse(
            external_request_id=external_request_id, business_outcome=outcome,
            observed_parameters=observed,
            external_result_id=self._new_id("extres"), observed_at=self._clock(),
            finality=self._finality)
