"""The bounded execution seam (ADR 5D, D-1 … D-5): the only path from a grant to the executor.

The act, in order:

1. read the clock **once**; that instant is the dispatch instant, and the executor is
   handed a clock that returns it, so the executor reads no wall clock either;
2. load the grant, the reservation, the authorization and its envelope; refuse an unknown
   grant, a reservation that is not ``RESERVED`` or whose lease has lapsed, an expired grant
   and a non-``AUTHORIZED`` authorization;
3. prove the grant: re-mint the credential request through the 5X minter from the
   presented reservation, authorization, envelope and target scope at the grant's own
   window and require the grant's request digest to re-derive (D-2);
4. address the target and the operation; refuse a scope the executor cannot address or an
   action type it has no operation for;
5. resolve the effective mode (D-3) and narrow the target policy to the grant's role (D-4);
6. mint the operations-local ``ExecutionAuthorization`` with the seam as issuer, signed by
   a verifier the seam constructs for this act, bounds and delta from the role, target from
   the scope, and the execution key's serialized form as the idempotency key (D-1, D-2);
7. in an applying mode, ``mark_dispatched`` before the executor runs; execute exactly one
   bounded change; ``record_observation`` after with the outcome mapped (D-5);
8. mint the record and the RA-8 effect observation, persist the record, and return.

A second dispatch for the same grant and dispatch request id replays the stored record.
Rollback is a second bounded action; a bare-policy rollback is refused (D-4).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from risk_authority.api import RiskAuthorityApplication
from risk_authority.domain.enums import ActionGateDecision
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope
from ugence_cloud_scaling_credential_broker import (
    CredentialBrokerPort,
    CredentialGrant,
    CredentialGrantStore,
    CredentialRequestMinter,
    CredentialRequestRefused,
    ReferenceCredentialBroker,
    REFERENCE_BROKER_AUTHORITY_ID,
)
from ugence_cloud_scaling_operations.authority import ReferenceAuthorityVerifier
from ugence_cloud_scaling_operations.config import OperationsConfig
from ugence_cloud_scaling_operations.contracts import (
    ExecutionAuthorization,
    ExecutionIntegrityError,
    ExecutionMode,
    ExecutionOutcome,
    ExecutionRequest,
)
from ugence_cloud_scaling_operations.executors import ControlledScalingExecutor, ReadinessEvaluator
from ugence_cloud_scaling_operations.rollback_coordinator import RollbackAuthorization
from ugence_execution_reservation import (
    ExecutionReservationPort,
    InMemoryExecutionReservationStore,
    ReservationState,
)
from ugence_risk_authority_execution_assurance.contracts import EffectObservation

from .errors import (
    BarePolicyRollbackRefused,
    BoundedExecutionConfigurationError,
    BoundedExecutionContractError,
    BoundedExecutionExactTypeError,
)
from .identifiers import DEFAULT_DISPATCH_DEADLINE, ISSUER_ID, RECORD_SCHEMA_VERSION, SIGNATURE_ALGORITHM
from .mapping import (
    OpsTarget,
    business_outcome_for,
    finality_for,
    ledger_outcome_for,
    ops_action_for,
    ops_target_for,
    to_epoch,
)
from .posture import LivePosture, narrow_target_policy, resolve_effective_mode
from .record import (
    BoundedExecutionRecord,
    BoundedExecutionRecordStore,
    InMemoryBoundedExecutionRecordStore,
    RecordDisposition,
    derive_record_id,
    effect_observation_for,
)
from .refusals import DispatchRefusal

__all__ = ["BoundedDispatch", "BoundedDispatchOutcome", "ExecutorParts", "BoundedExecutionSeam"]

_APPLYING = (ExecutionMode.SIMULATION, ExecutionMode.LIVE)


def _token(name: str, value: object) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise BoundedExecutionExactTypeError(f"{name} must be a non-blank str without surrounding whitespace")


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class BoundedDispatch:
    """What a caller may say. No instant, no mode, no bounds, no target address, no backend."""

    tenant_id: str
    grant_id: str
    reservation_id: str
    authorization_id: str
    target_scope: ExecutionTargetScope
    dispatch_request_id: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "grant_id", "reservation_id", "authorization_id", "dispatch_request_id"):
            _token(name, getattr(self, name))
        if type(self.target_scope) is not ExecutionTargetScope:
            raise BoundedExecutionExactTypeError("target_scope must be exactly an ExecutionTargetScope")
        if self.target_scope.tenant_id != self.tenant_id:
            raise BoundedExecutionExactTypeError("target_scope.tenant_id must equal the request tenant_id")


@dataclass(frozen=True)
class BoundedDispatchOutcome:
    """A record and its observation, or a typed refusal, at one instant."""

    dispatched_at: datetime
    effective_mode: Optional[ExecutionMode] = None
    mode_reasons: tuple[str, ...] = ()
    record: Optional[BoundedExecutionRecord] = None
    observation: Optional[EffectObservation] = None
    refusal: Optional[DispatchRefusal] = None
    detail: str = ""

    @property
    def dispatched(self) -> bool:
        return self.record is not None

    @property
    def applied(self) -> bool:
        """``True`` only when a LIVE mutation was applied."""

        return self.record is not None and self.record.applied

    @property
    def replayed(self) -> bool:
        return self.record is not None and self.record.disposition is RecordDisposition.REPLAYED


@dataclass(frozen=True)
class ExecutorParts:
    """What the deployment supplies for the executor. A backend is what the grant handle opens,
    built outside this repository; the seam never builds one."""

    config: OperationsConfig
    backend: Optional[Any] = None
    audit_sink: Optional[Any] = None
    idempotency_store: Optional[Any] = None
    readiness: Optional[ReadinessEvaluator] = None
    outcome_recorder: Optional[Any] = None


class BoundedExecutionSeam:
    """Compose the ladder's last step. Construct via ``production`` or ``reference``."""

    def __init__(
        self,
        *,
        app: RiskAuthorityApplication,
        reservations: ExecutionReservationPort,
        grants: CredentialGrantStore,
        broker: Optional[CredentialBrokerPort],
        records: BoundedExecutionRecordStore,
        parts: ExecutorParts,
        clock: Callable[[], datetime],
        dispatch_deadline: timedelta,
        production: bool,
    ) -> None:
        if not isinstance(app, RiskAuthorityApplication):
            raise BoundedExecutionConfigurationError("a RiskAuthorityApplication is required")
        if not callable(getattr(reservations, "get_reservation", None)) or not callable(
                getattr(reservations, "mark_dispatched", None)):
            raise BoundedExecutionConfigurationError("reservations must implement ExecutionReservationPort")
        if not callable(getattr(grants, "get", None)):
            raise BoundedExecutionConfigurationError("grants must implement CredentialGrantStore")
        if not callable(getattr(records, "get", None)) or not callable(getattr(records, "save", None)):
            raise BoundedExecutionConfigurationError("records must implement BoundedExecutionRecordStore")
        if type(parts) is not ExecutorParts or not isinstance(parts.config, OperationsConfig):
            raise BoundedExecutionConfigurationError("parts must be ExecutorParts over an OperationsConfig")
        if not callable(clock):
            raise BoundedExecutionConfigurationError("clock must be a callable returning an aware datetime")
        if type(dispatch_deadline) is not timedelta or dispatch_deadline <= timedelta(0):
            raise BoundedExecutionConfigurationError("dispatch_deadline must be a positive timedelta")
        self._app = app
        self._reservations = reservations
        self._grants = grants
        self._broker = broker
        self._records = records
        self._parts = parts
        self._clock = clock
        self._deadline = dispatch_deadline
        self._production = production
        self._minter = CredentialRequestMinter()

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(cls, *, app, reservations, grants, broker, records, parts: ExecutorParts, clock,
                   dispatch_deadline: timedelta = DEFAULT_DISPATCH_DEADLINE) -> "BoundedExecutionSeam":
        """Production seam. The posture is proven per act (D-3); construction only refuses
        what can never become production: a reference-mode application, the reference broker
        and the in-memory stores."""

        if getattr(app, "_production_mode", False) is not True:
            raise BoundedExecutionConfigurationError(
                "production bounded execution requires a RiskAuthorityApplication in production mode")
        if isinstance(broker, ReferenceCredentialBroker) or (
                getattr(broker, "is_production_authoritative", False) is not True):
            raise BoundedExecutionConfigurationError(
                "production bounded execution requires a production-authoritative broker; the reference "
                "broker is refused")
        if isinstance(reservations, InMemoryExecutionReservationStore):
            raise BoundedExecutionConfigurationError("the in-memory execution ledger is refused in production")
        if getattr(grants, "is_production_authoritative", False) is not True:
            raise BoundedExecutionConfigurationError("production bounded execution requires a production-authoritative grant store")
        if getattr(records, "is_production_authoritative", False) is not True:
            raise BoundedExecutionConfigurationError("production bounded execution requires a production-authoritative record store")
        return cls(app=app, reservations=reservations, grants=grants, broker=broker, records=records,
                   parts=parts, clock=clock, dispatch_deadline=dispatch_deadline, production=True)

    @classmethod
    def reference(cls, *, app, reservations, grants, parts: ExecutorParts, clock, broker=None, records=None,
                  dispatch_deadline: timedelta = DEFAULT_DISPATCH_DEADLINE) -> "BoundedExecutionSeam":
        """A labelled conformance seam. Never production: LIVE always resolves to DRY_RUN here."""

        if getattr(app, "_production_mode", False) is True:
            raise BoundedExecutionConfigurationError("the reference seam cannot be built over a production application")
        return cls(app=app, reservations=reservations, grants=grants, broker=broker,
                   records=records if records is not None else InMemoryBoundedExecutionRecordStore(),
                   parts=parts, clock=clock, dispatch_deadline=dispatch_deadline, production=False)

    @property
    def is_production(self) -> bool:
        return self._production

    # ------------------------------------------------------------------ posture (D-3)
    def posture_for(self, grant: CredentialGrant) -> LivePosture:
        broker_ok = self._broker is not None and not isinstance(self._broker, ReferenceCredentialBroker) \
            and getattr(self._broker, "is_production_authoritative", False) is True
        ledger_ok = not isinstance(self._reservations, InMemoryExecutionReservationStore) and (
            getattr(self._reservations, "production_mode", False) is True
            or getattr(self._reservations, "is_production_authoritative", False) is True)
        return LivePosture(
            production_application=getattr(self._app, "_production_mode", False) is True,
            production_ledger=ledger_ok,
            production_grant_store=getattr(self._grants, "is_production_authoritative", False) is True,
            production_broker=broker_ok,
            non_reference_grant_handle=(not grant.handle_ref.startswith("inert:")
                                        and grant.broker_authority_id != REFERENCE_BROKER_AUTHORITY_ID),
            backend_injected=self._parts.backend is not None,
            readiness_required=bool(self._parts.config.require_readiness),
        )

    # ------------------------------------------------------------------ the act
    def dispatch(self, request: BoundedDispatch) -> BoundedDispatchOutcome:
        if type(request) is not BoundedDispatch:
            raise BoundedExecutionExactTypeError("dispatch requires a BoundedDispatch")
        now = self._clock()  # the one clock read of this act
        if not _is_aware(now):
            raise BoundedExecutionContractError("the injected clock must return a timezone-aware instant")
        R = DispatchRefusal

        def refuse(reason: DispatchRefusal, detail: str) -> BoundedDispatchOutcome:
            return BoundedDispatchOutcome(dispatched_at=now, refusal=reason, detail=detail)

        # Replay: the same grant and dispatch request id name one record, forever.
        record_id = derive_record_id(request.tenant_id, request.grant_id, request.dispatch_request_id)
        stored = self._records.get(request.tenant_id, record_id)
        if stored is not None:
            replayed = replace(stored, disposition=RecordDisposition.REPLAYED)
            return BoundedDispatchOutcome(dispatched_at=now, effective_mode=ExecutionMode(stored.effective_mode),
                                          record=replayed, observation=effect_observation_for(replayed),
                                          detail="stored record returned; nothing dispatched")
        # 2. The artifacts.
        grant = self._grants.get(request.tenant_id, request.grant_id)
        if grant is None:
            return refuse(R.GRANT_NOT_FOUND, "no grant under this tenant and id")
        reservation = self._reservations.get_reservation(request.reservation_id)
        if reservation is None or reservation.tenant_id != request.tenant_id:
            return refuse(R.RESERVATION_NOT_FOUND, "no reservation under this tenant and id")
        if reservation.state is not ReservationState.RESERVED:
            return refuse(R.RESERVATION_NOT_RESERVED, f"reservation state is {reservation.state.value}")
        if reservation.lease.is_expired_at(now) or reservation.is_abandoned_at(now):
            return refuse(R.LEASE_EXPIRED, "the reservation lease has lapsed")
        if not grant.validity.is_valid_at(now):
            return refuse(R.GRANT_EXPIRED, "the grant is not valid at this instant")
        authorization = self._app.authorizations.get(request.tenant_id, request.authorization_id)
        if authorization is None:
            return refuse(R.AUTHORIZATION_NOT_FOUND, "no authorization under this tenant and id")
        if authorization.decision is not ActionGateDecision.AUTHORIZED:
            return refuse(R.AUTHORIZATION_NOT_AUTHORIZED, f"decision is {authorization.decision.value}")
        envelope = self._app.envelopes.get(request.tenant_id, authorization.envelope_id)
        if envelope is None:
            return refuse(R.ENVELOPE_NOT_FOUND, "the authorization's envelope is not in the store")
        # 3. Prove the grant: it must re-derive from exactly these artifacts (D-2).
        try:
            rederived = self._minter.mint(
                authorization=authorization, reservation=reservation, envelope=envelope,
                target_scope=request.target_scope, issued_at=grant.validity.issued_at,
                not_after=grant.validity.expires_at)
        except CredentialRequestRefused as exc:
            name = getattr(exc.refusal, "value", str(exc.refusal))
            return refuse(R.TARGET_SCOPE_MISMATCH if "TARGET" in name else R.GRANT_NOT_REDERIVED,
                          f"{name}: {exc.detail}")
        if rederived.request_digest != grant.request_digest or grant.tenant_id != request.tenant_id:
            return refuse(R.GRANT_NOT_REDERIVED, "the grant's request digest does not re-derive from these artifacts")
        if reservation.execution_key.serialized != rederived.execution_key.serialized:
            return refuse(R.GRANT_NOT_REDERIVED, "the reservation key is not the grant's execution key")
        # 4. Address the target and the operation.
        try:
            target = ops_target_for(request.target_scope)
            action = ops_action_for(request.target_scope.action_type)
        except BoundedExecutionContractError as exc:
            reason = R.ACTION_NOT_DISPATCHABLE if "action_type" in str(exc) else R.TARGET_NOT_ADDRESSABLE
            return refuse(reason, str(exc))
        # 5. Mode and blast radius (D-3, D-4).
        posture = self.posture_for(grant)
        effective, reasons = resolve_effective_mode(self._parts.config.mode, posture)
        policy = narrow_target_policy(self._parts.config, target, max_magnitude=grant.role.max_magnitude,
                                      max_delta=grant.role.max_delta)
        config = replace(self._parts.config, mode=effective, target_policy=policy)
        # 6. The operations-local authorization, issued and signed by this seam for this act.
        verifier = ReferenceAuthorityVerifier(issuer_secrets={ISSUER_ID: self._act_key(grant)},
                                              require_signature=True)
        scope = request.target_scope
        unsigned = ExecutionAuthorization(
            authorization_id=authorization.authorization_id,
            decision_id=envelope.decision_id,
            recommendation_id=authorization.action_digest,
            tenant_id=request.tenant_id,
            actor_id=envelope.subject,
            authority_source=ISSUER_ID,
            issued_at=to_epoch(grant.validity.issued_at),
            expires_at=to_epoch(min(grant.validity.expires_at, authorization.expires_at)),
            permitted_action=action,
            target_cluster=target.cluster,
            target_namespace=target.namespace,
            target_resource=target.resource,
            current_replicas=scope.magnitude_before,
            minimum_replicas=0,
            maximum_replicas=grant.role.max_magnitude,
            maximum_delta=grant.role.max_delta,
            reason=f"bounded {scope.action_type} under grant {grant.grant_id}",
            policy_version=grant.credential_profile,
            idempotency_key=reservation.execution_key.serialized,
            nonce=grant.grant_id,
            issuer=ISSUER_ID,
            signature_algorithm=SIGNATURE_ALGORITHM,
            key_id=grant.grant_id,
        )
        ops_authorization = replace(unsigned, signature=verifier.sign(unsigned, ISSUER_ID))
        ops_request = ExecutionRequest(
            action=action, target_cluster=target.cluster, target_namespace=target.namespace,
            target_resource=target.resource, current_replicas=scope.magnitude_before,
            target_replicas=scope.requested_magnitude, recommendation_id=authorization.action_digest,
            idempotency_key=reservation.execution_key.serialized, correlation_id=request.reservation_id,
            observed_at=to_epoch(now))
        epoch_now = to_epoch(now)
        executor = ControlledScalingExecutor(
            config, backend=self._parts.backend, verifier=verifier,
            idempotency_store=self._parts.idempotency_store, audit_sink=self._parts.audit_sink,
            readiness=self._parts.readiness, outcome_recorder=self._parts.outcome_recorder,
            clock=lambda: epoch_now)
        # 7. Dispatch: the ledger before the executor, the executor once, the ledger after (D-5).
        applying = effective in _APPLYING
        if applying:
            self._reservations.mark_dispatched(reservation.reservation_id, request.dispatch_request_id,
                                               dispatch_deadline=now + self._deadline, as_of=now)
        try:
            receipt = executor.execute(ops_request, ops_authorization, tenant_id=request.tenant_id,
                                       actor_id=envelope.subject)
        except ExecutionIntegrityError as exc:
            if applying:
                self._reservations.record_observation(reservation.reservation_id, record_id,
                                                      ledger_outcome_for(business_outcome_for("failed")), as_of=now)
            return refuse(R.EXECUTOR_INTEGRITY, str(exc))
        business = business_outcome_for(receipt.outcome)
        if applying:
            self._reservations.record_observation(reservation.reservation_id, record_id,
                                                  ledger_outcome_for(business), as_of=now)
        # 8. The record and the observation.
        record = BoundedExecutionRecord(
            schema_version=RECORD_SCHEMA_VERSION,
            record_id=record_id,
            tenant_id=request.tenant_id,
            grant_id=grant.grant_id,
            reservation_id=reservation.reservation_id,
            execution_key=reservation.execution_key.serialized,
            target_scope_digest=scope.digest(),
            envelope_id=envelope.envelope_id,
            authorized_action_digest=authorization.action_digest,
            request_digest=grant.request_digest,
            attempt_id=request.dispatch_request_id,
            external_request_id=receipt.audit_event_id or request.dispatch_request_id,
            effective_mode=effective.value,
            mode_reasons=tuple(reasons),
            ops_outcome=receipt.outcome,
            business_outcome=business,
            finality=finality_for(receipt.outcome, applying),
            applied=bool(receipt.applied),
            pre_state=receipt.pre_state,
            post_state=receipt.post_state,
            requested_magnitude=scope.requested_magnitude,
            dispatched_at=now,
            observed_at=now,
            receipt_hash=receipt.receipt_hash(),
            denial_reason=receipt.denial_reason,
        )
        self._records.save(record)
        return BoundedDispatchOutcome(dispatched_at=now, effective_mode=effective, mode_reasons=tuple(reasons),
                                      record=record, observation=effect_observation_for(record))

    # ------------------------------------------------------------------ rollback (D-4)
    @staticmethod
    def rollback(authorization: RollbackAuthorization) -> None:
        """Rollback is a second bounded action: a new admission, reservation and grant, then
        :meth:`dispatch` toward the prior record's ``pre_state``. There is no shortcut; a bare
        policy is refused, and so is a full authorization presented outside the ladder."""

        if type(authorization) is not RollbackAuthorization:
            raise BoundedExecutionExactTypeError("rollback requires a RollbackAuthorization")
        if authorization.authorization is None:
            raise BarePolicyRollbackRefused(
                "a rollback on a bare RollbackPolicy is refused: roll back through a second bounded "
                "dispatch with its own admission, reservation and grant (ADR 5D, D-4)")
        raise BarePolicyRollbackRefused(
            "a rollback carrying an ExecutionAuthorization is refused here: the seam mints the only "
            "operations-local authorization, from a grant; present a second BoundedDispatch instead")

    @staticmethod
    def rollback_target_for(record: BoundedExecutionRecord) -> Optional[int]:
        """The magnitude a rollback dispatch must request: the prior record's ``pre_state``."""

        if type(record) is not BoundedExecutionRecord:
            raise BoundedExecutionExactTypeError("rollback_target_for requires a BoundedExecutionRecord")
        return record.pre_state

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _act_key(grant: CredentialGrant) -> str:
        """The per-act HMAC key for the executor's signature gate. It exists only so the
        executor's own verifier runs unchanged; it never leaves the act and protects nothing
        across a trust boundary. Recorded as a carried gap in the ADR."""

        return hashlib.sha256(("ugence.bounded-execution|" + grant.grant_id + "|" + grant.request_digest)
                              .encode("utf-8")).hexdigest()
