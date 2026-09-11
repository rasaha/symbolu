"""The OpenAI Responses adapter behind the Model Egress Unit's provider seam.

Order of operations, and why it is this order:

1. **Pre-flight** (:meth:`OpenAIResponsesProvider._refusal`, pure): authorization names
   this vendor and exactly the designated snapshot; the request is unexpired, its
   content still hashes to its digest, and it is inside the LP-5 ceiling
   (:func:`ugence_model_egress_unit.check_request`); the injected transport declares
   itself non-production while commissioning is not ``MET``. The unit calls this
   before marking dispatch, so a refusable request never looks dispatched.
2. **Custody**: a lease is asked for, with an audit event either way. A refusal here
   is terminal and consumes nothing.
3. **Reserve, then dispatch** (LP-5, two-layer): the call budget is reserved *before*
   the transport is called, and nothing gives it back. The in-memory
   :class:`ugence_model_egress_unit.CallBudget` is the safety ceiling for tests and
   fake-transport development; the durable twin is the exchange's
   ``commissioning_reservation`` (migration 2) and wiring it in front of this adapter
   is LP-6 step 7 work, not this module.
4. **Retry**: once, and only for an outcome whose transport *proved* no bytes were
   dispatched. Anything ambiguous is recorded ``OUTCOME_UNKNOWN`` with a
   :class:`DispatchAttempt`, not retried.
5. **Record**: never ``genuine_call: true``. The fake transport cannot claim it; a
   transport that does, outside ``MET``, is an invariant violation and this adapter
   raises rather than write a record it cannot stand behind — the leased row then
   expires into ``OUTCOME_UNKNOWN`` by the unit's existing reconciliation.

The adapter does not select, raise, waive or reinterpret a limit: ``limits`` is the
frozen :data:`COMMISSIONING_LIMITS` and the class exposes nothing that changes it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from ugence_model_egress_unit import (
    COMMISSIONING_LIMITS,
    COMMISSIONING_STATUS,
    BudgetExhausted,
    CallBudget,
    CommissioningLimits,
    CredentialLease,
    CredentialRequest,
    CustodyAuditEvent,
    CustodyRefused,
    DispatchAttempt,
    EgressRequest,
    EgressResult,
    OPENAI_RESPONSES,
    ProviderRefusedInProduction,
    RefusalReason,
    check_request,
    materialize_with_audit,
)

from .transport import FakeTransport, OutcomeKind, PreparedRequest, TransportOutcome
from .version import ADAPTER_ID, DESIGNATED_MODEL, VENDOR

__all__ = [
    "ESTIMATED_CENTS_PER_CALL",
    "GenuineResponseNotRecordable",
    "prepare",
    "OpenAIResponsesProvider",
]

#: The cost reserved per call, before dispatch. Deliberately the budget divided by the
#: call ceiling, so the ten permitted calls and the USD 25 budget exhaust together and
#: no estimate of a "cheap" call can stretch the count. Conservative by construction.
ESTIMATED_CENTS_PER_CALL = COMMISSIONING_LIMITS.budget_usd_cents // COMMISSIONING_LIMITS.max_genuine_calls


class GenuineResponseNotRecordable(RuntimeError):
    """A transport returned a genuine vendor response while no record may carry one.

    Raised rather than recorded: a refusal would misstate a call that consumed budget,
    and a response record would claim ``genuine_call: true`` against the release gate.
    The unit's lease expiry reconciles the row as ``OUTCOME_UNKNOWN``, which is the
    truthful state.
    """


def prepare(request: EgressRequest, *, limits: CommissioningLimits = COMMISSIONING_LIMITS) -> PreparedRequest:
    """The exact Responses request for ``request``. Pure. Raises rather than widens."""

    violation = check_request(request, limits)
    if violation is not None:
        raise violation
    if request.minimized_context is None:
        raise ValueError("a purged request has no content to send")
    messages = [{"role": "user", "content": unit.text} for unit in request.minimized_context]
    return PreparedRequest(url=OPENAI_RESPONSES.url, body={
        "model": request.authorization.authorized_model,
        "input": messages,
        "max_output_tokens": request.parameters["max_output_tokens"],
        "store": False,
        "stream": False,
    })


def _output_text(body: Mapping[str, Any]) -> Optional[str]:
    """The response text, from either Responses shape; ``None`` when there is none."""

    text = body.get("output_text")
    if isinstance(text, str):
        return text
    parts = []
    for item in body.get("output") or ():
        if not isinstance(item, Mapping):
            continue
        for content in item.get("content") or ():
            if isinstance(content, Mapping) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "".join(parts) if parts else None


def _total_tokens(body: Mapping[str, Any]) -> Optional[int]:
    usage = body.get("usage")
    if isinstance(usage, Mapping):
        total = usage.get("total_tokens")
        if isinstance(total, int) and not isinstance(total, bool):
            return total
    return None


class OpenAIResponsesProvider:
    """LP-3's adapter, MEU-only, with an injected transport and no default one."""

    NON_PRODUCTION = True
    maturity = "REFERENCE_GRADE_SHADOW_ONLY"
    vendor = VENDOR
    designated_model = DESIGNATED_MODEL

    def __init__(self, *, transport, custody, budget: CallBudget,
                 credential_profile: str, adapter_id: str = ADAPTER_ID,
                 audit_sink: Optional[Callable[[CustodyAuditEvent], None]] = None) -> None:
        if transport is None or not callable(getattr(transport, "send", None)):
            raise TypeError("a transport must be injected; this adapter has no default")
        if not isinstance(budget, CallBudget):
            raise TypeError("the budget is a CallBudget")
        if budget.limits is not COMMISSIONING_LIMITS:
            raise ValueError("the adapter runs under COMMISSIONING_LIMITS and nothing else")
        self.adapter_id = adapter_id
        self._transport = transport
        self._custody = custody
        self._budget = budget
        self._credential_profile = credential_profile
        self._audit_sink = audit_sink

    @property
    def limits(self) -> CommissioningLimits:
        """Read-only: the frozen LP-5 constants. There is no setter, by design."""

        return COMMISSIONING_LIMITS

    # -- pre-flight ---------------------------------------------------------------

    def _refusal(self, request: EgressRequest, now: datetime) -> Optional[RefusalReason]:
        auth = request.authorization
        if not auth.authorizes(vendor=self.vendor, model=auth.authorized_model,
                               tenant_id=request.tenant_id):
            return RefusalReason.TARGET_NOT_AUTHORIZED
        violation = check_request(request, COMMISSIONING_LIMITS)
        if violation is not None:
            return violation.reason
        if auth.authorized_model != self.designated_model:
            return RefusalReason.MODEL_NOT_AVAILABLE
        if now >= request.not_valid_after:
            return RefusalReason.REQUEST_NOT_VALID
        if request.minimized_context is None or not request.content_matches_digest():
            return RefusalReason.CONTENT_DIGEST_MISMATCH
        if COMMISSIONING_STATUS != "MET" and getattr(self._transport, "NON_PRODUCTION", False) is not True:
            return RefusalReason.LIVE_EGRESS_NOT_AVAILABLE
        if (self._budget.calls_reserved >= COMMISSIONING_LIMITS.max_genuine_calls
                or self._budget.in_flight >= COMMISSIONING_LIMITS.concurrency
                or self._budget.cents_reserved + ESTIMATED_CENTS_PER_CALL > COMMISSIONING_LIMITS.budget_usd_cents):
            return RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED
        return None

    # -- execution ----------------------------------------------------------------

    def _refused(self, request: EgressRequest, now: datetime, reason: RefusalReason) -> EgressResult:
        return EgressResult.refused(
            request_id=request.request_id, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, recorded_at=now,
            adapter_id=self.adapter_id, reason=reason,
            model_ref=request.authorization.authorized_model)

    def _unknown(self, request: EgressRequest, now: datetime, reason: str) -> EgressResult:
        return EgressResult.outcome_unknown(
            request_id=request.request_id, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, recorded_at=now,
            attempt=DispatchAttempt(adapter_id=self.adapter_id, dispatch_observed_at=now,
                                    detected_at=now, reason=reason))

    def execute(self, request: EgressRequest, *, now: datetime,
                production: bool = False) -> EgressResult:
        if production:
            raise ProviderRefusedInProduction(
                f"{self.adapter_id} refuses a production posture while commissioning is "
                f"{COMMISSIONING_STATUS}; only the owner's separate MET statement, released as "
                f"a new version of the unit, changes that.")
        reason = self._refusal(request, now)
        if reason is not None:
            return self._refused(request, now, reason)
        prepared = prepare(request)  # exact destination and shape, or an exception

        lease, _event = materialize_with_audit(
            self._custody,
            CredentialRequest(request_id=request.request_id, tenant_id=request.tenant_id,
                              vendor=self.vendor, credential_profile=self._credential_profile,
                              requested_at=now),
            now=now, production=production, sink=self._audit_sink)
        if lease is None:
            return self._refused(request, now, RefusalReason.CREDENTIAL_NOT_COMMISSIONED)
        if lease.is_production_authoritative and COMMISSIONING_STATUS != "MET":
            return self._refused(request, now, RefusalReason.LIVE_EGRESS_NOT_AVAILABLE)
        if lease.expired(now):
            # Validation row 11: a lease expired at use is a custody refusal, decided
            # before any reservation and before any dispatch.
            return self._refused(request, now, RefusalReason.CREDENTIAL_NOT_COMMISSIONED)

        try:
            self._budget.reserve(estimated_cents=ESTIMATED_CENTS_PER_CALL, now=now,
                                 request_id=str(request.request_id))
        except BudgetExhausted:
            return self._refused(request, now, RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED)
        try:
            outcome = self._dispatch(prepared, lease, now)
        except CustodyRefused:
            # ``CredentialLease.use`` refused before handing the secret to the transport:
            # nothing was dispatched. The reservation is kept (non-compensatory).
            return self._refused(request, now, RefusalReason.CREDENTIAL_NOT_COMMISSIONED)
        except Exception:  # noqa: BLE001 — a raising transport is an ambiguous dispatch
            return self._unknown(request, now, "transport raised during dispatch; state ambiguous")
        finally:
            self._budget.release_in_flight()

        if outcome.kind is OutcomeKind.DISPATCHED_NO_RESPONSE:
            return self._unknown(request, now, outcome.detail or "no conclusive response")
        if outcome.kind is OutcomeKind.TRANSIENT_BEFORE_DISPATCH:
            return EgressResult.failed(
                request_id=request.request_id, tenant_id=request.tenant_id,
                correlation_id=request.correlation_id, recorded_at=now,
                adapter_id=self.adapter_id, model_ref=request.authorization.authorized_model)
        if outcome.genuine:
            raise GenuineResponseNotRecordable(
                f"{self.adapter_id}: the transport reported a genuine vendor response while "
                f"commissioning is {COMMISSIONING_STATUS}; no record may carry genuine_call: true")
        text = _output_text(outcome.body or {})
        if outcome.status != 200 or text is None:
            return EgressResult.failed(
                request_id=request.request_id, tenant_id=request.tenant_id,
                correlation_id=request.correlation_id, recorded_at=now,
                adapter_id=self.adapter_id, model_ref=request.authorization.authorized_model)
        return EgressResult.answered(
            request_id=request.request_id, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, recorded_at=now,
            adapter_id=self.adapter_id, payload=text,
            model_ref=request.authorization.authorized_model,
            token_count=_total_tokens(outcome.body or {}))

    def _dispatch(self, prepared: PreparedRequest, lease: CredentialLease, now: datetime) -> TransportOutcome:
        attempts = 0
        while True:
            attempts += 1
            outcome = lease.use(
                lambda secret: self._transport.send(prepared, bearer=secret, now=now), now=now)
            if not isinstance(outcome, TransportOutcome):
                raise TypeError("a transport answers with a TransportOutcome")
            if outcome.retryable and self._budget.may_retry(
                    attempts_so_far=attempts, failure_class=OutcomeKind.TRANSIENT_BEFORE_DISPATCH.value):
                continue
            return outcome
