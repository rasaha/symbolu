"""The adapter behind the real review service (AI-A), over the real SQLite ledger and
the adapter double: a decision proven by a real signature is recorded
``IDP_AUTHENTICATED`` with its authentication reference, and the identity-ADR rows
the service owns still hold with this adapter in the seam. The token itself reaches
neither the ledger, the runtime signal nor the outcome."""

from __future__ import annotations

from ugence_approval_workflow import ApprovalState, ApproverKind, ApproverRef, ReviewDecision, \
    StaticApproverEligibility
from ugence_governed_review_service import (
    IDP_AUTHENTICATED,
    TENANT_SOURCE_PROOF,
    DecisionResult,
    ReviewService,
    StaticRunReader,
    TenantMode,
    VerifiedClaims,
    authentication_reference,
    subject_reference,
)

from ugence_approver_identity_jwt import JwtApproverIdentityAdapter

import _service_fixtures as S
from conftest import ACTOR_CLAIM, STUDIO_AUDIENCE, TENANT_CLAIM, base_claims, config_for

F = S.F
FP = "d" * 64


def approver_for(issuer, subject: str) -> ApproverRef:
    """The presented reference: the issuer-qualified subject, as ID-2 requires."""

    probe = VerifiedClaims(issuer=issuer.issuer, subject=subject, audience=issuer.audience,
                           authenticated_at=F.T0, expires_at=F.T0)
    return ApproverRef(approver_id=subject_reference(probe), approver_kind=ApproverKind.HUMAN,
                       role=F.ROLE, authority_reference=f"directory://roles/{F.ROLE}")


def world(tmp_path, issuer, clock):
    alice, bob = approver_for(issuer, "alice"), approver_for(issuer, "bob")
    ledger = F.sqlite_ledger(tmp_path, alice, bob)
    adapter_double = S.RecordingAdapter(known=("i1",))
    port = JwtApproverIdentityAdapter(config_for(issuer, tenant_claim=TENANT_CLAIM),
                                      clock=clock.datetime)
    svc = ReviewService(
        ledger=ledger, adapter=adapter_double, reader=StaticRunReader(
            {"i1": S.parked_checkpoint("i1", "t1", FP)}),
        tenant_id=F.TENANT, clock=clock.datetime,
        eligibility=StaticApproverEligibility((alice, bob)),
        identity_port=port, tenant_mode=TenantMode.SINGLE_TENANT,
    )
    approval_id = S.request_for(ledger, clock, "i1", fingerprint=FP).approval_id
    return dict(ledger=ledger, double=adapter_double, svc=svc, approval_id=approval_id,
                alice=alice, bob=bob, port=port)


def _tokenless(w, token):
    for signal in w["double"].signals:
        assert token not in str(signal)
    for event in w["ledger"].approval_events(w["approval_id"]):
        assert token not in str(event.to_dict())


def test_a_signed_proof_records_an_idp_authenticated_decision_with_its_reference(
        tmp_path, issuer, clock):
    w = world(tmp_path, issuer, clock)
    claims = base_claims(issuer, **{TENANT_CLAIM: F.TENANT})
    token = issuer.mint(claims, kid="rsa-1")
    out = w["svc"].submit_decision(approval_id=w["approval_id"], decision=ReviewDecision.GRANT,
                                   presented_approver=w["alice"], justification="ok",
                                   presented_proof=token)
    assert out.result is DecisionResult.RECORDED
    assert out.identity_proof == IDP_AUTHENTICATED
    assert out.approval.decided_by == w["alice"].approver_id == "https%3A%2F%2Fissuer.test|alice"
    expected = w["port"].authenticate(token).claims
    assert out.authentication_reference == authentication_reference(expected)
    assert out.tenant_source == TENANT_SOURCE_PROOF
    assert out.assurance.to_dict()["amr"] == ["pwd", "otp"]
    payload = w["double"].signals[0][2]
    assert payload["identity_proof"] == IDP_AUTHENTICATED
    assert payload["authentication_reference"] == out.authentication_reference
    assert w["double"].resumes == ["i1"]
    assert token not in str(out)
    _tokenless(w, token)


def test_rows_1_2_5_6_7_and_14_hold_with_the_real_adapter_in_the_seam(tmp_path, issuer, clock):
    w = world(tmp_path, issuer, clock)
    submit = lambda proof, approver=None: w["svc"].submit_decision(  # noqa: E731
        approval_id=w["approval_id"], decision=ReviewDecision.GRANT,
        presented_approver=approver or w["alice"], justification="ok", presented_proof=proof)

    def pending():
        return w["ledger"].state_at(w["approval_id"], as_of=clock.datetime()) is ApprovalState.PENDING

    # row 14: a proof audience-bound to the studio is refused by the service.
    studio = issuer.mint(base_claims(issuer, aud=STUDIO_AUDIENCE), kid="rsa-1")
    assert submit(studio).result is DecisionResult.REFUSED_UNAUTHENTICATED and pending()
    # row 1: no proof, or a forged one.
    assert submit("").result is DecisionResult.REFUSED_UNAUTHENTICATED
    forged = issuer.mint(base_claims(issuer), kid="rsa-1", pem=issuer.foreign_pem())
    assert submit(forged).result is DecisionResult.REFUSED_UNAUTHENTICATED and pending()
    # row 2: Alice's proof, Bob presented.
    alice_token = issuer.mint(base_claims(issuer), kid="rsa-1")
    assert submit(alice_token, w["bob"]).result is DecisionResult.REFUSED_IDENTITY_MISMATCH
    # row 5: a proof whose actor claim does not say human never decides.
    service_token = issuer.mint(base_claims(issuer, **{ACTOR_CLAIM: None}), kid="rsa-1")
    assert submit(service_token).result is DecisionResult.REFUSED_NOT_HUMAN and pending()
    # row 7: the issuer's keys unreachable for an unknown kid.
    issuer.fail_next = 3
    ghost = issuer.mint(base_claims(issuer), kid="rsa-1", headers={"kid": "ghost"})
    out = submit(ghost)
    assert out.result is DecisionResult.REFUSED_IDENTITY_UNAVAILABLE and pending()
    assert "KeyRetrievalFailed" in out.reason
    issuer.fail_next = 0
    # row 6: the proof expires between the read and the write.
    assert w["svc"].list_queue()
    clock.advance(hours=2)
    assert submit(alice_token).result is DecisionResult.REFUSED_UNAUTHENTICATED and pending()
    assert w["double"].signals == []
    for token in (studio, forged, alice_token, service_token, ghost):
        _tokenless(w, token)
