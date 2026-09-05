"""AI-A: the approver identity port and the proof shape, at unit level, over the real
SQLite ledger and the adapter double.

Failure-matrix rows of ``ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md`` §4 proven here:
1, 2, 3, 4, 5, 6, 7, 8, 10, 11 and 12. Rows 9 (ledger and linkage carry the
reference), 13 (the assurance gate) and 14 (the studio relay) belong to AI-D, AI-E and
AI-B and are not claimed.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ugence_approval_workflow import (
    ApprovalState,
    ApproverKind,
    ApproverRef,
    ReviewDecision,
    StaticApproverEligibility,
)

from ugence_governed_review_service import (
    IDENTITY_PROOF,
    IDP_AUTHENTICATED,
    PRESENTED_UNPROVEN,
    PROOF_HEADER,
    TENANT_SOURCE_CONFIGURED,
    TENANT_SOURCE_PROOF,
    ActorKind,
    ApproverIdentity,
    ApproverIdentityPort,
    ContractViolation,
    DecisionResult,
    IdentityUnavailable,
    ReviewService,
    StaticApproverIdentityAdapter,
    StaticRunReader,
    TenantMode,
    VerifiedClaims,
    authentication_reference,
    subject_reference,
)

import _service_fixtures as S

F = S.F
FP = "b" * 64
ISSUER = "issuer.example"
AUDIENCE = "ugence-governed-review-service"


def claims_for(subject: str, *, tenants=(F.TENANT,), acr="", amr=(), issued_at=None,
               lifetime=timedelta(hours=1), proof_id_digest="") -> VerifiedClaims:
    at = issued_at or F.T0
    return VerifiedClaims(issuer=ISSUER, subject=subject, audience=AUDIENCE,
                          authenticated_at=at, expires_at=at + lifetime,
                          tenant_claims=tuple(tenants), acr=acr, amr=tuple(amr),
                          proof_id_digest=proof_id_digest)


def approver_for(claims: VerifiedClaims, role: str = F.ROLE) -> ApproverRef:
    """The presented reference for a proven subject: the issuer-qualified subject as
    the id, the directory grant as the authority reference (ID-2)."""

    return ApproverRef(approver_id=subject_reference(claims), approver_kind=ApproverKind.HUMAN,
                       role=role, authority_reference=f"directory://roles/{role}")


ALICE = claims_for("alice", amr=("pwd", "otp"), acr="urn:example:loa2")
BOB = claims_for("bob")
ALICE_REF, BOB_REF = approver_for(ALICE), approver_for(BOB)


@pytest.fixture()
def world(tmp_path):
    clock = F.Clock()
    # The directory (the ledger's eligibility port) knows Alice and Bob by their
    # issuer-qualified subjects: row 3's mapping is string equality, by convention.
    ledger = F.sqlite_ledger(tmp_path, ALICE_REF, BOB_REF)
    adapter = S.RecordingAdapter(known=("i1",))
    reader = StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)})
    port = StaticApproverIdentityAdapter(unavailable=("proof-down",))
    port.register_human("proof-alice", ALICE)
    port.register_human("proof-bob", BOB)
    svc = ReviewService(
        ledger=ledger, adapter=adapter, reader=reader, tenant_id=F.TENANT,
        clock=clock.datetime, eligibility=StaticApproverEligibility((ALICE_REF, BOB_REF)),
        identity_port=port, tenant_mode=TenantMode.SINGLE_TENANT,
    )
    record = S.request_for(ledger, clock, "i1", fingerprint=FP)
    return {"clock": clock, "ledger": ledger, "adapter": adapter, "svc": svc, "port": port,
            "approval_id": record.approval_id, "reader": reader}


def submit(w, *, proof, approver=ALICE_REF, decision=ReviewDecision.GRANT, approval_id=None):
    return w["svc"].submit_decision(approval_id=approval_id or w["approval_id"],
                                    decision=decision, presented_approver=approver,
                                    justification="ok", presented_proof=proof)


def pending(w) -> bool:
    state = w["ledger"].state_at(w["approval_id"], as_of=w["clock"].datetime())
    return state is ApprovalState.PENDING


# --------------------------------------------------------------------------- #
# the shape: ID-2 and ID-3
# --------------------------------------------------------------------------- #
def test_the_port_is_structurally_compatible_with_the_decision_authority_seam():
    """authenticate(...) -> (actor_id, actor_type, authenticated), plus the claims."""

    port = StaticApproverIdentityAdapter()
    assert isinstance(port, ApproverIdentityPort)
    identity = port.register_human("p", ALICE)
    answered = port.authenticate("p")
    assert (answered.actor_id, answered.actor_type.value, answered.authenticated) \
        == (subject_reference(ALICE), "HUMAN", True)
    assert answered.claims == ALICE
    unknown = port.authenticate("nobody")
    assert (unknown.actor_id, unknown.actor_type, unknown.authenticated, unknown.claims) \
        == ("", ActorKind.SYSTEM, False, None)
    assert identity.proof == PRESENTED_UNPROVEN


def test_the_subject_reference_is_issuer_qualified_and_unambiguous():
    a = claims_for("x|y")
    b = VerifiedClaims(issuer=f"{ISSUER}|x", subject="y", audience=AUDIENCE,
                       authenticated_at=F.T0, expires_at=F.T0 + timedelta(hours=1))
    assert subject_reference(a) != subject_reference(b)
    assert subject_reference(ALICE) == "issuer.example|alice"


def test_the_authentication_reference_is_deterministic_digest_bound_and_never_the_proof():
    ref = authentication_reference(ALICE)
    assert ref.startswith("authn:sha256:") and len(ref) == len("authn:sha256:") + 64
    assert authentication_reference(claims_for("alice", amr=("pwd", "otp"),
                                               acr="urn:example:loa2")) == ref
    for changed in (
        claims_for("alice", amr=("pwd",), acr="urn:example:loa2"),
        claims_for("alice", amr=("pwd", "otp")),
        claims_for("alice", amr=("pwd", "otp"), acr="urn:example:loa2", tenants=("tenant-b",)),
        claims_for("alice", amr=("pwd", "otp"), acr="urn:example:loa2", lifetime=timedelta(2)),
        claims_for("alice", amr=("pwd", "otp"), acr="urn:example:loa2",
                   proof_id_digest="sha256:" + "0" * 64),
    ):
        assert authentication_reference(changed) != ref
    # The proof string plays no part: the same claims behind two proofs reference alike.
    port = StaticApproverIdentityAdapter()
    port.register_human("one", ALICE)
    port.register_human("two", ALICE)
    assert authentication_reference(port.authenticate("one").claims) \
        == authentication_reference(port.authenticate("two").claims)


def test_the_claims_shape_refuses_a_raw_proof_id_naive_instants_and_a_mislabelled_answer():
    with pytest.raises(ContractViolation):
        claims_for("alice", proof_id_digest="raw-id-123")
    with pytest.raises(ContractViolation):
        VerifiedClaims(issuer=ISSUER, subject="s", audience=AUDIENCE,
                       authenticated_at=F.T0.replace(tzinfo=None), expires_at=F.T0)
    with pytest.raises(ContractViolation):
        ApproverIdentity("someone-else", ActorKind.HUMAN, True, ALICE)
    with pytest.raises(ContractViolation):
        ApproverIdentity(subject_reference(ALICE), ActorKind.HUMAN, True, ALICE, proof="PROVEN")
    with pytest.raises(ContractViolation):
        ApproverIdentity(subject_reference(ALICE), ActorKind.HUMAN, True, None)


def test_the_static_adapter_never_labels_an_answer_authenticated_and_is_refused_in_production(
        tmp_path):
    port = StaticApproverIdentityAdapter()
    port.register("p", ApproverIdentity(subject_reference(ALICE), ActorKind.HUMAN, True, ALICE,
                                        proof=IDP_AUTHENTICATED))
    assert port.authenticate("p").proof == PRESENTED_UNPROVEN
    assert port.NON_PRODUCTION is True
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    with pytest.raises(ContractViolation, match="production"):
        ReviewService(ledger=ledger, adapter=S.RecordingAdapter(), reader=StaticRunReader(),
                      tenant_id=F.TENANT, clock=clock.datetime, identity_port=port,
                      tenant_mode=TenantMode.SINGLE_TENANT, production=True)
    with pytest.raises(ContractViolation, match="tenant_mode"):
        ReviewService(ledger=ledger, adapter=S.RecordingAdapter(), reader=StaticRunReader(),
                      tenant_id=F.TENANT, clock=clock.datetime, identity_port=port)
    with pytest.raises(ContractViolation, match="ApproverIdentityPort"):
        ReviewService(ledger=ledger, adapter=S.RecordingAdapter(), reader=StaticRunReader(),
                      tenant_id=F.TENANT, clock=clock.datetime, identity_port=object(),
                      tenant_mode=TenantMode.SINGLE_TENANT)


# --------------------------------------------------------------------------- #
# the happy path with a proof
# --------------------------------------------------------------------------- #
def test_a_proven_decision_is_recorded_under_the_issuer_qualified_subject(world):
    out = submit(world, proof="proof-alice")
    assert out.result is DecisionResult.RECORDED
    assert out.approval.decided_by == subject_reference(ALICE) == "issuer.example|alice"
    assert out.approval.decided_authority_reference == "directory://roles/risk-approver"
    assert out.authentication_reference == authentication_reference(ALICE)
    assert out.authentication_reference != out.approval.decided_authority_reference
    assert out.approval.signature_reference == ""
    assert out.identity_proof == PRESENTED_UNPROVEN == IDENTITY_PROOF, \
        "the fixture adapter proves nothing; only a real adapter says IDP_AUTHENTICATED"
    assert out.tenant_source == TENANT_SOURCE_PROOF
    assert out.assurance.to_dict() == {"acr": "urn:example:loa2", "amr": ["pwd", "otp"],
                                       "threshold_enforced": False, "policy_reference": ""}
    payload = world["adapter"].signals[0][2]
    assert payload["decided_by"] == subject_reference(ALICE)
    assert payload["authentication_reference"] == out.authentication_reference
    assert payload["tenant_id"] == F.TENANT and payload["tenant_source"] == TENANT_SOURCE_PROOF
    assert payload["assurance"]["amr"] == ["pwd", "otp"]
    assert world["adapter"].resumes == ["i1"]


# --------------------------------------------------------------------------- #
# rows 1, 2, 5, 6, 7: refused before any record changes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("proof, result, fragment", [
    ("", DecisionResult.REFUSED_UNAUTHENTICATED, "no proof"),                      # row 1
    ("proof-unknown", DecisionResult.REFUSED_UNAUTHENTICATED, "does not authenticate"),  # row 1
    ("proof-down", DecisionResult.REFUSED_IDENTITY_UNAVAILABLE, "IdentityUnavailable"),  # row 7
])
def test_rows_01_and_07_no_proof_unknown_proof_or_unreachable_issuer_changes_nothing(
        world, proof, result, fragment):
    out = submit(world, proof=proof)
    assert out.result is result and not out.recorded and fragment in out.reason
    assert pending(world) and world["adapter"].signals == [] and world["adapter"].resumes == []
    assert out.authentication_reference == "" and out.assurance is None


def test_row_07_any_failure_of_the_port_fails_closed_not_open(world):
    class Broken:
        def authenticate(self, proof):
            raise RuntimeError("boom")

    svc = ReviewService(ledger=world["ledger"], adapter=world["adapter"], reader=world["reader"],
                        tenant_id=F.TENANT, clock=world["clock"].datetime,
                        identity_port=Broken(), tenant_mode=TenantMode.SINGLE_TENANT)
    out = svc.submit_decision(approval_id=world["approval_id"], decision=ReviewDecision.GRANT,
                              presented_approver=ALICE_REF, presented_proof="anything")
    assert out.result is DecisionResult.REFUSED_IDENTITY_UNAVAILABLE and "RuntimeError" in out.reason
    assert "boom" not in out.reason, "the port's message is not relayed"
    assert pending(world) and world["adapter"].signals == []


def test_row_02_authenticated_as_alice_presenting_bob_is_refused(world):
    out = submit(world, proof="proof-alice", approver=BOB_REF)
    assert out.result is DecisionResult.REFUSED_IDENTITY_MISMATCH
    assert pending(world) and world["adapter"].signals == []
    # The bare subject is not the issuer-qualified subject either.
    bare = ApproverRef(approver_id="alice", approver_kind=ApproverKind.HUMAN, role=F.ROLE)
    assert submit(world, proof="proof-alice", approver=bare).result \
        is DecisionResult.REFUSED_IDENTITY_MISMATCH


@pytest.mark.parametrize("kind", [ActorKind.AI, ActorKind.SYSTEM])
def test_row_05_an_ai_or_service_actor_with_a_human_role_grant_never_decides(world, kind):
    world["port"].register_actor("proof-agent", ALICE, kind)  # same grant, not a human
    out = submit(world, proof="proof-agent")
    assert out.result is DecisionResult.REFUSED_NOT_HUMAN and kind.value in out.reason
    assert pending(world) and world["adapter"].signals == []


def test_row_06_a_proof_that_expired_between_read_and_write_is_refused_at_the_write(world):
    assert world["svc"].list_queue()  # the read proves nothing about the proof
    world["clock"].advance(hours=2)
    out = submit(world, proof="proof-alice")
    assert out.result is DecisionResult.REFUSED_UNAUTHENTICATED and "expired" in out.reason
    assert pending(world) and world["adapter"].signals == []


# --------------------------------------------------------------------------- #
# row 3: authentication alone authorizes nothing
# --------------------------------------------------------------------------- #
def test_row_03_a_proven_subject_that_is_not_a_directory_principal_is_ineligible(world):
    carol = claims_for("carol")
    world["port"].register_human("proof-carol", carol)
    out = submit(world, proof="proof-carol", approver=approver_for(carol))
    assert out.result is DecisionResult.REFUSED_INELIGIBLE
    assert out.approval.decided_by == "" and pending(world)
    assert world["adapter"].signals == []


# --------------------------------------------------------------------------- #
# rows 4, 11, 12: the tenant comes from the proof (ID-4)
# --------------------------------------------------------------------------- #
def test_row_04_a_proof_for_another_tenant_is_not_reviewable_here(world):
    world["port"].register_human("proof-alice-b", claims_for("alice", tenants=("tenant-b",)))
    out = submit(world, proof="proof-alice-b")
    assert out.result is DecisionResult.REFUSED_NOT_REVIEWABLE and "tenant-b" in out.reason
    assert pending(world) and world["adapter"].signals == []


def test_row_11_single_tenant_with_no_tenant_claim_uses_the_configured_tenant_and_says_so(world):
    world["port"].register_human("proof-alice-nt", claims_for("alice", tenants=()))
    out = submit(world, proof="proof-alice-nt")
    assert out.result is DecisionResult.RECORDED
    assert out.tenant_source == TENANT_SOURCE_CONFIGURED
    assert world["adapter"].signals[0][2]["tenant_source"] == TENANT_SOURCE_CONFIGURED
    assert world["adapter"].signals[0][2]["tenant_id"] == F.TENANT


def test_row_12_multi_tenant_refuses_a_missing_or_ambiguous_claim_and_records_a_matching_one(
        world):
    port = world["port"]
    port.register_human("proof-alice-nt", claims_for("alice", tenants=()))
    port.register_human("proof-alice-two", claims_for("alice", tenants=(F.TENANT, "tenant-b")))
    svc = ReviewService(ledger=world["ledger"], adapter=world["adapter"], reader=world["reader"],
                        tenant_id=F.TENANT, clock=world["clock"].datetime,
                        eligibility=StaticApproverEligibility((ALICE_REF,)),
                        identity_port=port, tenant_mode=TenantMode.MULTI_TENANT)

    def go(proof):
        return svc.submit_decision(approval_id=world["approval_id"],
                                   decision=ReviewDecision.GRANT, presented_approver=ALICE_REF,
                                   presented_proof=proof)

    missing = go("proof-alice-nt")
    assert missing.result is DecisionResult.REFUSED_TENANT_UNPROVEN and "MULTI_TENANT" in missing.reason
    ambiguous = go("proof-alice-two")
    assert ambiguous.result is DecisionResult.REFUSED_TENANT_UNPROVEN and "more than one" in ambiguous.reason
    assert pending(world) and world["adapter"].signals == []
    ok = go("proof-alice")
    assert ok.result is DecisionResult.RECORDED and ok.tenant_source == TENANT_SOURCE_PROOF


def test_an_ambiguous_tenant_claim_is_refused_in_single_tenant_mode_too(world):
    world["port"].register_human("proof-alice-two", claims_for("alice", tenants=(F.TENANT, "tenant-b")))
    out = submit(world, proof="proof-alice-two")
    assert out.result is DecisionResult.REFUSED_TENANT_UNPROVEN and pending(world)


# --------------------------------------------------------------------------- #
# row 8: replay is per proven subject
# --------------------------------------------------------------------------- #
def test_row_08_a_replay_needs_the_same_proven_subject_not_only_the_same_outcome(world):
    first = submit(world, proof="proof-alice")
    assert first.result is DecisionResult.RECORDED
    again = submit(world, proof="proof-alice")
    assert again.result is DecisionResult.REPLAYED
    assert again.authentication_reference == first.authentication_reference
    other = submit(world, proof="proof-bob", approver=BOB_REF)
    assert other.result is DecisionResult.REFUSED_ALREADY_DECIDED
    assert subject_reference(ALICE) in other.reason
    # Bob cannot borrow Alice's presented reference either: the binding refuses first.
    assert submit(world, proof="proof-bob", approver=ALICE_REF).result \
        is DecisionResult.REFUSED_IDENTITY_MISMATCH
    # The replay re-delivered the signal and, the fixture instance still parked, the resume.
    assert len(world["adapter"].signals) == 2 and world["adapter"].resumes == ["i1", "i1"]


# --------------------------------------------------------------------------- #
# row 10: assurance is recorded, never enforced (ID-5)
# --------------------------------------------------------------------------- #
def test_row_10_a_proof_without_amr_is_recorded_and_the_decision_stands(world):
    out = submit(world, proof="proof-bob", approver=BOB_REF)
    assert out.result is DecisionResult.RECORDED
    assert out.assurance.to_dict() == {"acr": "", "amr": [], "threshold_enforced": False,
                                       "policy_reference": ""}
    assert world["adapter"].signals[0][2]["assurance"] == {"acr": "", "amr": [],
                                                           "threshold_enforced": False,
                                                           "policy_reference": ""}


# --------------------------------------------------------------------------- #
# without a port nothing changes
# --------------------------------------------------------------------------- #
def test_without_a_port_a_proof_is_ignored_and_the_legacy_path_is_labelled(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    adapter = S.RecordingAdapter(known=("i1",))
    svc = S.service(ledger, clock, adapter=adapter,
                    reader=StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)}),
                    eligibility=StaticApproverEligibility((F.APPROVER,)))
    assert svc.tenant_mode is TenantMode.SINGLE_TENANT and not svc.identity_port_configured
    aid = S.request_for(ledger, clock, "i1", fingerprint=FP).approval_id
    out = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                              presented_approver=F.APPROVER, presented_proof="ignored")
    assert out.result is DecisionResult.RECORDED and out.identity_proof == PRESENTED_UNPROVEN
    assert out.authentication_reference == "" and out.assurance is None
    assert out.tenant_source == TENANT_SOURCE_CONFIGURED
    assert svc.read_run("i1")["tenant_mode"] == "SINGLE_TENANT"


# --------------------------------------------------------------------------- #
# the wire: the proof travels in one header and never comes back
# --------------------------------------------------------------------------- #
def test_http_reads_the_proof_header_hands_it_to_the_port_and_never_echoes_it(world):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from ugence_governed_review_service import build_app

    body = {"approval_id": world["approval_id"], "decision": "GRANT",
            "presented_approver": ALICE_REF.to_dict(), "justification": "ok"}
    with TestClient(build_app(world["svc"])) as c:
        refused = c.post("/review/decisions", json=body)
        assert refused.status_code == 409
        assert refused.json()["result"] == "REFUSED_UNAUTHENTICATED"
        r = c.post("/review/decisions", json=body, headers={PROOF_HEADER: "proof-alice"})
        assert r.status_code == 200
        answer = r.json()
        assert answer["result"] == "RECORDED"
        assert answer["authentication_reference"] == authentication_reference(ALICE)
        assert answer["tenant_source"] == TENANT_SOURCE_PROOF
        assert answer["assurance"]["amr"] == ["pwd", "otp"]
        assert "proof-alice" not in r.text and "proof-alice" not in str(r.headers)
        run = c.get("/review/runs/i1").json()
        assert run["tenant_mode"] == "SINGLE_TENANT" and "proof-alice" not in str(run)
