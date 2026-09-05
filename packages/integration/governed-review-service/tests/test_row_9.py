"""AI-D, identity-ADR row 9, as the review service owns it: a proven decision's
``authentication_reference`` is recorded on the approval and in its hash-linked event;
altering ``decided_by`` or the reference is detected by the ledger; recomputing the
reference from the verified claims detects a substituted reference; and a replay
reports the reference the ledger holds, not the resubmission's."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

from ugence_approval_workflow import (
    ApprovalState,
    ApproverKind,
    ApproverRef,
    ArtifactIntegrityError,
    ReviewDecision,
    SqliteApprovalWorkflowStore,
    StaticApproverEligibility,
)

from ugence_governed_review_service import (
    IDENTITY_PROOF,
    DecisionResult,
    ReviewService,
    StaticApproverIdentityAdapter,
    StaticRunReader,
    TenantMode,
    VerifiedClaims,
    authentication_reference,
    subject_reference,
    verify_authentication_reference,
)

import _service_fixtures as S

F = S.F
FP = "e" * 64
ISSUER = "issuer.example"
AUDIENCE = "ugence-governed-review-service"


def claims_for(subject: str, **over) -> VerifiedClaims:
    kwargs = dict(issuer=ISSUER, subject=subject, audience=AUDIENCE, authenticated_at=F.T0,
                  expires_at=F.T0 + timedelta(hours=1), tenant_claims=(F.TENANT,),
                  acr="urn:example:loa2", amr=("pwd", "otp"), proof_id_digest="sha256:" + "1" * 64)
    kwargs.update(over)
    return VerifiedClaims(**kwargs)


ALICE = claims_for("alice")
ALICE_REF = ApproverRef(approver_id=subject_reference(ALICE), approver_kind=ApproverKind.HUMAN,
                        role=F.ROLE, authority_reference=f"directory://roles/{F.ROLE}")


def world(tmp_path):
    clock = F.Clock()
    ledger = F.sqlite_ledger(tmp_path, ALICE_REF)
    adapter = S.RecordingAdapter(known=("i1",))
    port = StaticApproverIdentityAdapter()
    port.register_human("proof-alice", ALICE)
    # A second proof for the same subject with a later authentication: same
    # decided_by, different reference.
    port.register_human("proof-alice-later",
                        claims_for("alice", authenticated_at=F.T0 + timedelta(minutes=1),
                                   proof_id_digest="sha256:" + "2" * 64))
    svc = ReviewService(
        ledger=ledger, adapter=adapter, reader=StaticRunReader(
            {"i1": S.parked_checkpoint("i1", "t1", FP)}),
        tenant_id=F.TENANT, clock=clock.datetime,
        eligibility=StaticApproverEligibility((ALICE_REF,)),
        identity_port=port, tenant_mode=TenantMode.SINGLE_TENANT,
    )
    approval_id = S.request_for(ledger, clock, "i1", fingerprint=FP).approval_id
    return dict(clock=clock, ledger=ledger, adapter=adapter, svc=svc, approval_id=approval_id)


def submit(w, proof):
    return w["svc"].submit_decision(approval_id=w["approval_id"], decision=ReviewDecision.GRANT,
                                    presented_approver=ALICE_REF, justification="ok",
                                    presented_proof=proof)


def test_a_proven_decision_records_the_reference_on_the_approval_and_in_its_event(tmp_path):
    w = world(tmp_path)
    out = submit(w, "proof-alice")
    assert out.result is DecisionResult.RECORDED
    expected = authentication_reference(ALICE)
    assert out.authentication_reference == expected
    assert out.approval.authentication_reference == expected
    assert out.approval.signature_reference == ""
    assert out.approval.decided_authority_reference == ALICE_REF.authority_reference
    assert out.identity_proof == IDENTITY_PROOF, "the fixture adapter proves nothing (AI-A)"
    stored = w["ledger"].get_approval(w["approval_id"])
    assert stored.authentication_reference == expected
    granted = [e for e in w["ledger"].approval_events(w["approval_id"])
               if e.event_type is ApprovalState.GRANTED]
    assert json.loads(granted[0].detail)["authentication_reference"] == expected
    assert w["ledger"].verify_chain()
    assert w["adapter"].signals[0][2]["authentication_reference"] == expected


def test_a_decision_without_a_proof_records_no_reference(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    svc = S.service(ledger, clock, adapter=S.RecordingAdapter(known=("i1",)),
                    reader=StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)}),
                    eligibility=StaticApproverEligibility((F.APPROVER,)))
    aid = S.request_for(ledger, clock, "i1", fingerprint=FP).approval_id
    out = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                              presented_approver=F.APPROVER, justification="ok")
    assert out.result is DecisionResult.RECORDED
    assert out.authentication_reference == "" and out.approval.authentication_reference == ""
    assert "authentication_reference" not in out.approval.to_dict()
    assert "authentication_reference" not in json.loads(ledger.approval_events(aid)[-1].detail)


def test_the_reference_recomputed_from_the_claims_detects_a_substitution(tmp_path):
    w = world(tmp_path)
    recorded = submit(w, "proof-alice").approval.authentication_reference
    assert verify_authentication_reference(ALICE, recorded)
    for altered in (
        claims_for("alice", amr=("pwd",)),
        claims_for("alice", acr=""),
        claims_for("alice", tenant_claims=("tenant-b",)),
        claims_for("alice", authenticated_at=F.T0 + timedelta(seconds=1)),
        claims_for("alice", proof_id_digest=""),
        claims_for("bob"),
    ):
        assert not verify_authentication_reference(altered, recorded)
    assert not verify_authentication_reference(ALICE, recorded[:-1] + "0")
    assert not verify_authentication_reference(ALICE, "")


def test_altering_decided_by_or_the_reference_after_the_fact_is_detected(tmp_path):
    w = world(tmp_path)
    submit(w, "proof-alice")
    recorded = authentication_reference(ALICE)
    path = w["ledger"].path
    w["ledger"].close()

    raw = sqlite3.connect(path)
    raw.execute("UPDATE approvals SET record_json=replace(record_json, ?, ?)",
                (f'"decided_by":"{ALICE_REF.approver_id}"', '"decided_by":"mallory"'))
    raw.commit()
    reopened = SqliteApprovalWorkflowStore(path, StaticApproverEligibility((ALICE_REF,)))
    try:
        reopened.get_approval(w["approval_id"])
    except ArtifactIntegrityError:
        pass
    else:
        raise AssertionError("an altered decided_by re-derived its artifact digest")
    reopened.close()
    # Put decided_by back; alter the reference in the event instead.
    raw.execute("UPDATE approvals SET record_json=replace(record_json, ?, ?)",
                ('"decided_by":"mallory"', f'"decided_by":"{ALICE_REF.approver_id}"'))
    raw.execute("DROP TRIGGER ledger_events_no_update")
    raw.execute("UPDATE ledger_events SET detail_json=replace(detail_json, ?, ?)",
                (recorded, "authn:sha256:" + "f" * 64))
    raw.commit()
    raw.close()
    reopened = SqliteApprovalWorkflowStore(path, StaticApproverEligibility((ALICE_REF,)))
    assert reopened.get_approval(w["approval_id"]).authentication_reference == recorded
    assert reopened.verify_chain() is False
    reopened.close()


def test_a_replay_under_a_fresh_proof_reports_the_recorded_reference(tmp_path):
    w = world(tmp_path)
    first = submit(w, "proof-alice")
    again = submit(w, "proof-alice-later")
    assert again.result is DecisionResult.REPLAYED
    assert again.authentication_reference == first.authentication_reference
    assert again.approval.authentication_reference == first.authentication_reference
    assert w["ledger"].verify_chain()
