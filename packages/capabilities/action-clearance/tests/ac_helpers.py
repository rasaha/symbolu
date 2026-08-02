"""Shared builders for Action Clearance tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_action_clearance import (
    ActionClearanceEvaluator,
    AuthorizationContext,
    AuthorizedActionIdentity,
    ClearancePolicy,
    ClearancePolicyContext,
    ClearanceRequest,
    SignalBundle,
    SignalProvenance,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    TrustedSignal,
)


from ugence_action_clearance import (  # noqa: E402
    ActionClearanceEvaluator,
    AuthorizationContext,
    AuthorizedActionIdentity,
    ClearancePolicy,
    ClearancePolicyContext,
    ClearanceRequest,
    SignalBundle,
    SignalProvenance,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    TrustedSignal,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "acme"
ACTFP = "ACTION-FP-001"
TARGET = "target-ref-1"
AUTHZ = "authz-ref-1"


def ts(t=T0, **kw):
    base = dict(hours=0)
    base.update(kw)
    return t + timedelta(**base)


def signal(signal_type, value, *, subject=TARGET, status=SignalStatus.PRESENT,
           valid_until=None, captured_at=T0, tenant=TENANT, signal_id=None,
           integrity_digest=None, provenance=None, authorization_ref=None,
           action_fingerprint=None):
    return TrustedSignal(
        signal_id=signal_id or f"sig-{signal_type.value}",
        signal_type=signal_type, tenant_id=tenant, subject_ref=subject,
        source_ref="source-1", source_kind="test-source", captured_at=captured_at,
        status=status, value=value, provenance_ref="prov-ref-1",
        valid_until=valid_until if valid_until is not None else ts(hours=2),
        integrity_digest=integrity_digest, provenance=provenance,
        authorization_ref=authorization_ref, action_fingerprint=action_fingerprint)


def provenance(trust=SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION, source_kind="test-source",
               adapter_id="adapter-a", adapter_version="1.0.0"):
    return SignalProvenance(source_id="src-1", source_kind=source_kind,
                            ingestion_boundary="boundary-1", trust_level=trust,
                            provenance_ref="prov-ref-1", adapter_id=adapter_id,
                            adapter_version=adapter_version)


def authorization(outcome="AUTHORIZED", expires=None, issued=None,
                  constraints=(), obligations=("REQUIRE_AUDIT_LOG",), structured=()):
    return AuthorizationContext(
        authorization_ref=AUTHZ, authorization_result_fingerprint="agr-fp-1",
        authorization_outcome=outcome, authorization_issued_at=issued or ts(hours=-1),
        authorization_expires_at=expires or ts(hours=1), tenant_id=TENANT,
        authorization_constraints=tuple(constraints), authorization_obligations=tuple(obligations),
        decision_record_ref="dec-1", context_envelope_ref="cer-1",
        context_envelope_hash="cerhash", authorized_actor_basis="actor-basis",
        policy_refs=("repo-policy:v1",), structured_constraints=tuple(structured))


def action(fp=ACTFP, target=TARGET, operation="apply", action_type="merge", **kw):
    return AuthorizedActionIdentity(authorized_action_fingerprint=fp, action_type=action_type,
                                    target_ref=target, operation=operation, **kw)


def policy(required=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY), **kw):
    return ClearancePolicy(policy_id="clearance-policy", policy_version="v1",
                           required_signal_types=tuple(required), **kw)


def request(signals, *, auth=None, act=None, evaluation_time=T0,
            required=(SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY),
            profile="neutral", skew=None, max_lifetime=None):
    return ClearanceRequest(
        request_id="req-1", tenant_id=TENANT, evaluation_time=evaluation_time,
        authorization=auth or authorization(), action=act or action(),
        signals=SignalBundle(signals=tuple(signals), required_signal_types=tuple(required)),
        policy=ClearancePolicyContext(profile_id=profile, policy_refs=("repo-policy:v1",),
                                      clock_skew_tolerance_s=skew, max_clearance_lifetime_s=max_lifetime))


def happy_signals():
    return [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]


