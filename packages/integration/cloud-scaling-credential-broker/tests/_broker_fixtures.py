"""The genuine chain, extended by clearance and reservation: 5C's world, an admitted action,
a genuine CLEAR receipt from the Action Clearance evaluator, and a reservation in the
in-memory execution ledger. This module adds nothing of its own to the authority chain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ugence_action_clearance import (
    AuthorizationContext,
    AuthorizedActionIdentity,
    ClearancePolicy,
    ClearancePolicyContext,
    ClearanceReceiptBody,
    ClearanceRequest,
    SignalBundle,
    SignalStatus,
    SignalType,
    TrustedSignal,
    evaluate_clearance,
)
from ugence_execution_reservation import (
    ClearanceReceipt,
    ExecutionKey,
    InMemoryExecutionReservationStore,
    ReservationResult,
)

from _admission_fixtures import ADMISSION_INSTANT, admission_request, build_admission_world, production_app

from ugence_cloud_scaling_credential_broker import (
    CredentialBrokerSeam,
    CredentialMaterializationRequest,
)

__all__ = [
    "BROKER_INSTANT", "RESERVATION_INSTANT", "RESERVATION_TTL_S", "World",
    "build_broker_world", "materialization_request", "clear_receipt_for", "reserve",
    "production_app",
]

RESERVATION_INSTANT: datetime = ADMISSION_INSTANT + timedelta(seconds=2)
BROKER_INSTANT: datetime = ADMISSION_INSTANT + timedelta(seconds=3)
RESERVATION_TTL_S = 600


def _signal(tenant, signal_type, value, *, subject, captured_at):
    return TrustedSignal(
        signal_id=f"sig-{signal_type.value}", signal_type=signal_type, tenant_id=tenant,
        subject_ref=subject, source_ref="source-1", source_kind="test-source", captured_at=captured_at,
        status=SignalStatus.PRESENT, value=value, provenance_ref="prov-ref-1",
        valid_until=captured_at + timedelta(hours=2))


def clear_receipt_for(authorization, action, target_scope, *, evaluation_time: datetime) -> ClearanceReceipt:
    """A genuine CLEAR receipt from the Action Clearance evaluator, bound to this authorization
    and this action's digest, with the target scope digest as target and the action type as
    operation — the same identities the execution key names."""

    tenant = authorization.tenant_id
    target_ref, operation = target_scope.digest(), target_scope.action_type
    request = ClearanceRequest(
        request_id="req-5x-1", tenant_id=tenant, evaluation_time=evaluation_time,
        authorization=AuthorizationContext(
            authorization_ref=authorization.authorization_id, authorization_result_fingerprint="agr-fp-1",
            authorization_outcome="AUTHORIZED", authorization_issued_at=evaluation_time - timedelta(seconds=1),
            authorization_expires_at=authorization.expires_at, tenant_id=tenant,
            authorization_constraints=(), authorization_obligations=(), decision_record_ref="dec-1",
            context_envelope_ref=authorization.envelope_id, context_envelope_hash="cerhash",
            authorized_actor_basis="envelope-subject", policy_refs=("repo-policy:v1",), structured_constraints=()),
        action=AuthorizedActionIdentity(authorized_action_fingerprint=action.digest, action_type=action.action_type,
                                        target_ref=target_ref, operation=operation),
        signals=SignalBundle(
            signals=(_signal(tenant, SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, subject=target_ref,
                             captured_at=evaluation_time),
                     _signal(tenant, SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": action.digest},
                             subject=target_ref, captured_at=evaluation_time)),
            required_signal_types=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY)),
        policy=ClearancePolicyContext(profile_id="neutral", policy_refs=("repo-policy:v1",)))
    policy = ClearancePolicy(policy_id="clearance-policy", policy_version="v1",
                             required_signal_types=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY))
    result = evaluate_clearance(request, policy)
    return ClearanceReceipt(body=ClearanceReceiptBody.from_result(result), created_at=result.evaluated_at,
                            target_ref=target_ref, operation=operation, profile_id="neutral",
                            action_governance_result_fingerprint="agr-fp-1",
                            decision_record_ref="dec-1", context_envelope_ref=authorization.envelope_id,
                            context_envelope_hash="cerhash")


def reserve(store, authorization, action, target_scope, *, as_of: datetime, ttl_s: int = RESERVATION_TTL_S):
    receipt = clear_receipt_for(authorization, action, target_scope, evaluation_time=as_of - timedelta(seconds=1))
    store.put_receipt(receipt)
    key = ExecutionKey(tenant_id=authorization.tenant_id, authorization_ref=authorization.authorization_id,
                       authorized_action_fingerprint=action.digest, target_ref=target_scope.digest(),
                       operation=target_scope.action_type)
    outcome = store.reserve_once(key, receipt.receipt_id, authorization.authorization_id, action.digest,
                                 ttl_s, as_of=as_of)
    assert outcome.result is ReservationResult.ACQUIRED, (outcome.result, outcome.reason)
    return outcome.reservation


@dataclass
class World:
    clock: Any
    app: Any
    candidate: Any
    envelope: Any
    authorization: Any
    action: Any
    reservations: InMemoryExecutionReservationStore
    reservation: Any

    @property
    def target_scope(self):
        return self.candidate.target_scope

    def seam(self, **overrides) -> CredentialBrokerSeam:
        kw = dict(app=self.app, reservations=self.reservations, clock=self.clock)
        kw.update(overrides)
        return CredentialBrokerSeam.reference(**kw)


def build_broker_world() -> World:
    admission_world = build_admission_world()
    admitted = admission_world.admission().admit(admission_request(admission_world))
    assert admitted.admitted, (admitted.refusal, admitted.detail)
    store = InMemoryExecutionReservationStore()
    reservation = reserve(store, admitted.authorization, admitted.action, admission_world.target_scope,
                          as_of=RESERVATION_INSTANT)
    clock = admission_world.clock
    clock.at = BROKER_INSTANT
    clock.reads = 0
    return World(clock=clock, app=admission_world.app, candidate=admission_world.candidate,
                 envelope=admission_world.envelope, authorization=admitted.authorization,
                 action=admitted.action, reservations=store, reservation=reservation)


def materialization_request(world: World, **overrides) -> CredentialMaterializationRequest:
    base = dict(tenant_id=world.candidate.tenant_id, authorization_id=world.authorization.authorization_id,
                reservation_id=world.reservation.reservation_id, target_scope=world.target_scope)
    base.update(overrides)
    return CredentialMaterializationRequest(**base)
