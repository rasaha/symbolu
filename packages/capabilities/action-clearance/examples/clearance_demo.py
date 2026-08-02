"""Offline deterministic Action Clearance demonstration (design §32).

No persistence, no reservation, no execution, no network. Run:

    PYTHONPATH=packages/capabilities/action-clearance/src \
        python packages/capabilities/action-clearance/examples/clearance_demo.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_action_clearance import (
    ActionClearanceEvaluator,
    AuthorizationContext,
    AuthorizedActionIdentity,
    ClearancePolicy,
    ClearancePolicyContext,
    ClearanceRequest,
    ClearanceStatus,
    ConstraintKind,
    ConsumptionStatus,
    EffectiveConstraint,
    SignalBundle,
    SignalStatus,
    SignalType,
    TrustedSignal,
)

CLOCK = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
TENANT, ACTFP, TARGET, AUTHZ = "tenant-acme", "action-fp-42", "repo/main", "authz-42"
REQUIRED = (SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY)


def _sig(stype, value, valid_until=None):
    return TrustedSignal(
        signal_id=f"sig-{stype.value}", signal_type=stype, tenant_id=TENANT,
        subject_ref=TARGET, source_ref="src", source_kind="test", captured_at=CLOCK,
        status=SignalStatus.PRESENT, value=value, provenance_ref="prov",
        valid_until=valid_until or CLOCK + timedelta(hours=2))


def _auth(**kw):
    return AuthorizationContext(
        authorization_ref=AUTHZ, authorization_result_fingerprint="agr-fp",
        authorization_outcome=kw.get("outcome", "AUTHORIZED"),
        authorization_issued_at=CLOCK - timedelta(hours=1),
        authorization_expires_at=kw.get("expires", CLOCK + timedelta(hours=1)),
        tenant_id=TENANT, authorization_obligations=("REQUIRE_AUDIT_LOG",),
        structured_constraints=(EffectiveConstraint("parallelism", ConstraintKind.MAX, 4),))


def _action(fp=ACTFP):
    return AuthorizedActionIdentity(authorized_action_fingerprint=fp, action_type="merge",
                                    target_ref=TARGET, operation="apply")


def _req(signals, auth=None, action=None):
    return ClearanceRequest(
        request_id="demo-req", tenant_id=TENANT, evaluation_time=CLOCK,
        authorization=auth or _auth(), action=action or _action(),
        signals=SignalBundle(tuple(signals), REQUIRED),
        policy=ClearancePolicyContext(profile_id="neutral", policy_refs=("repo:v1",)))


POLICY = ClearancePolicy(
    policy_id="clearance-policy", policy_version="v1", required_signal_types=REQUIRED,
    added_obligations=("REQUIRE_REVALIDATION_AT_DISPATCH",),
    clearance_constraints=(EffectiveConstraint("parallelism", ConstraintKind.MAX, 2),))


def run(verbose: bool = True) -> dict:
    ev = ActionClearanceEvaluator()
    out: dict = {}

    def show(step, r):
        if verbose:
            print(f"  [{step}] status={r.status.value:8} reasons={list(r.reason_codes)} "
                  f"valid_until={r.valid_until.isoformat()}")

    if verbose:
        print("== Action Clearance v0.1 — offline deterministic demonstration ==")

    # 1-4. authorized action + trusted mandatory signals -> CLEAR, bounded validity
    ok = [_sig(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
          _sig(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    r_clear = ev.evaluate(_req(ok), POLICY)
    show("1-4 CLEAR", r_clear)
    out["clear"] = r_clear.status.value
    out["clear_valid_until_bounded"] = r_clear.valid_until <= _auth().authorization_expires_at
    out["effective_constraints"] = list(r_clear.effective_constraints)
    out["obligations_superset"] = "REQUIRE_AUDIT_LOG" in r_clear.obligations

    # 5-6. remove one mandatory signal -> non-CLEAR (HOLD)
    r_missing = ev.evaluate(_req([ok[0]]), POLICY)
    show("5-6 missing", r_missing)
    out["missing"] = r_missing.status.value

    # 7-8. active freeze -> HOLD
    r_freeze = ev.evaluate(_req(ok + [_sig(SignalType.CHANGE_FREEZE, {"active": True})]), POLICY)
    show("7-8 freeze", r_freeze)
    out["freeze"] = r_freeze.status.value

    # 9-10. action-identity mismatch -> BLOCK
    bad = [ok[0], _sig(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": "different-fp"})]
    r_block = ev.evaluate(_req(bad), POLICY)
    show("9-10 mismatch", r_block)
    out["mismatch"] = r_block.status.value

    # 11-12. conflicting trusted signals -> ESCALATE (two available/unavailable
    #        target-availability facts disagree; neither alone blocks -> conflict)
    conflict = ok + [
        _sig(SignalType.TARGET_AVAILABILITY, {"available": True}),
        TrustedSignal(signal_id="target-avail-2", signal_type=SignalType.TARGET_AVAILABILITY,
                      tenant_id=TENANT, subject_ref=TARGET, source_ref="src2",
                      source_kind="test", captured_at=CLOCK, status=SignalStatus.PRESENT,
                      value={"available": False}, provenance_ref="p",
                      valid_until=CLOCK + timedelta(hours=2))]
    r_escalate = ev.evaluate(_req(conflict), POLICY)
    show("11-12 conflict", r_escalate)
    out["conflict"] = r_escalate.status.value

    # 13-14. replay identical input -> identical result fingerprint
    r_a = ev.evaluate(_req(ok), POLICY)
    r_b = ev.evaluate(_req(list(reversed(ok))), POLICY)
    out["replay_identical_fingerprint"] = r_a.result_fingerprint == r_b.result_fingerprint
    if verbose:
        print(f"  [13-14 replay] identical result_fingerprint={out['replay_identical_fingerprint']} "
              f"({r_a.result_id[:20]}…)")

    # 15. report boundaries
    if verbose:
        print("  [15] no persistence · no reservation · no execution — clearance is not execution")
        print("== demonstration complete ==")
    out["persistence"] = "NONE"
    out["reservation"] = "NONE"
    out["execution"] = "DISABLED"
    return out


if __name__ == "__main__":
    run()
