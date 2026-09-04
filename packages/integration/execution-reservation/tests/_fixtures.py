"""Shared builders: a *genuine* CLEAR result from the Action Clearance evaluator,
receipts wrapped for storage, execution keys, and both adapters."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

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
    SqliteExecutionReservationStore,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "acme"
ACTFP = "ACTION-FP-001"
TARGET = "target-ref-1"
AUTHZ = "authz-ref-1"
OPERATION = "apply"
PROFILE = "neutral"


def ts(**kw) -> datetime:
    return T0 + timedelta(**kw)


def signal(signal_type, value, *, subject=TARGET, status=SignalStatus.PRESENT,
           captured_at=T0, valid_until=None, signal_id=None):
    return TrustedSignal(
        signal_id=signal_id or f"sig-{signal_type.value}", signal_type=signal_type,
        tenant_id=TENANT, subject_ref=subject, source_ref="source-1", source_kind="test-source",
        captured_at=captured_at, status=status, value=value, provenance_ref="prov-ref-1",
        valid_until=valid_until if valid_until is not None else captured_at + timedelta(hours=2))


def authorization(expires=None):
    return AuthorizationContext(
        authorization_ref=AUTHZ, authorization_result_fingerprint="agr-fp-1",
        authorization_outcome="AUTHORIZED", authorization_issued_at=ts(hours=-1),
        authorization_expires_at=expires or ts(hours=1), tenant_id=TENANT,
        authorization_constraints=(), authorization_obligations=("REQUIRE_AUDIT_LOG",),
        decision_record_ref="dec-1", context_envelope_ref="cer-1",
        context_envelope_hash="cerhash", authorized_actor_basis="actor-basis",
        policy_refs=("repo-policy:v1",), structured_constraints=())


def action(fp=ACTFP, target=TARGET, operation=OPERATION):
    return AuthorizedActionIdentity(authorized_action_fingerprint=fp, action_type="merge",
                                    target_ref=target, operation=operation)


def policy():
    return ClearancePolicy(policy_id="clearance-policy", policy_version="v1",
                           required_signal_types=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY))


def request(signals, *, evaluation_time=T0, act=None, request_id="req-1"):
    return ClearanceRequest(
        request_id=request_id, tenant_id=TENANT, evaluation_time=evaluation_time,
        authorization=authorization(), action=act or action(),
        signals=SignalBundle(signals=tuple(signals),
                             required_signal_types=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY)),
        policy=ClearancePolicyContext(profile_id=PROFILE, policy_refs=("repo-policy:v1",)))


def happy_signals(captured_at=T0, fp=ACTFP):
    return [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, captured_at=captured_at),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": fp}, captured_at=captured_at)]


def clear_result(*, evaluation_time=T0, fp=ACTFP, extra_signals=(), request_id="req-1"):
    sigs = happy_signals(captured_at=evaluation_time, fp=fp) + list(extra_signals)
    result = evaluate_clearance(request(sigs, evaluation_time=evaluation_time,
                                        act=action(fp=fp), request_id=request_id), policy())
    return result


def blocked_result():
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "DISABLED"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    return evaluate_clearance(request(sigs), policy())


def receipt_for(result, *, created_at=None, target=TARGET, operation=OPERATION, profile=PROFILE,
                **meta) -> ClearanceReceipt:
    body = ClearanceReceiptBody.from_result(result)
    return ClearanceReceipt(body=body, created_at=created_at or result.evaluated_at,
                            target_ref=target, operation=operation, profile_id=profile,
                            action_governance_result_fingerprint="agr-fp-1",
                            decision_record_ref="dec-1", context_envelope_ref="cer-1",
                            context_envelope_hash="cerhash", **meta)


def key(fp=ACTFP, target=TARGET, operation=OPERATION, tenant=TENANT, authz=AUTHZ) -> ExecutionKey:
    return ExecutionKey(tenant_id=tenant, authorization_ref=authz, authorized_action_fingerprint=fp,
                        target_ref=target, operation=operation)


def sqlite_path(tmp_path=None) -> str:
    d = tmp_path or tempfile.mkdtemp(prefix="exres-")
    return os.path.join(str(d), "ledger.sqlite3")


def make_store(kind: str, tmp_path=None):
    if kind == "memory":
        return InMemoryExecutionReservationStore()
    return SqliteExecutionReservationStore(sqlite_path(tmp_path))


STORE_KINDS = ("memory", "sqlite")
