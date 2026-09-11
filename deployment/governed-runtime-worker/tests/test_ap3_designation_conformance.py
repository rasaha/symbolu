"""AP-3 designation record and its conformance harness (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
section 20; owner designation of 2026-09-11).

    IMPLEMENTATION AND CONFORMANCE EVIDENCE ONLY. Nothing here touches the real issuer.
    Section 20 says an in-process issuer never satisfies AP-3, and this module does not
    claim otherwise: it proves that the committed record's ``conformance_harness`` block
    describes what the ratified adapter and the plane's write gate actually do when
    configured with the designated issuer and audience and driven by in-process tokens
    shaped like Cloudflare Access tokens. The sixteen ``validation_matrix`` rows stay
    null until they run against the real issuer.

The record is read from disk; every designation value asserted below is the owner's,
and the file is scanned for anything token-, secret- or key-shaped.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ugence_approver_identity_jwt import AdapterConfig, JwtApproverIdentityAdapter
from ugence_approver_identity_jwt.errors import KeyRetrievalFailed
from ugence_authority_directory import SqliteAuthorityDirectory
from ugence_governed_review_service.identity import PROOF_HEADER

from governed_runtime_worker.authority_plane import IMPLEMENTED_WRITES, WRITE_PROOF_HEADER
from governed_runtime_worker.authority_reads import build_authority_reads
from governed_runtime_worker.authority_writes import build_authority_writes
from _issuer import InProcessIssuer
from conftest import NOW, PKG, TENANT, Clock

RECORD_PATH = PKG / "AP3_ENTERPRISE_ISSUER_VALIDATION.json"
EGRESS_PATH = PKG / "EXTERNAL_DEPLOYMENT_EVIDENCE.json"

DESIGNATED_ISSUER = "https://ugence.cloudflareaccess.com"
DESIGNATED_AUDIENCE = "24b3008ed1910d53caebbaffb3358aa801bd9dc5cf9f5af8aa7ada87335b12b3"
DESIGNATED_JWKS = "https://ugence.cloudflareaccess.com/cdn-cgi/access/certs"
TEST_PRINCIPAL = "ap3-test@ugence.ai"
TEST_GROUP = "ugence-ap3-test@ugence.ai"
KID = "cf-rsa-1"
ROLE = "risk-approver"
SCOPE = "approval/policy_pack"


def _record() -> dict:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# the record: designated, pending, secret-free
# --------------------------------------------------------------------------- #
def test_the_record_is_designated_and_pending_not_met():
    record = _record()
    assert record["ap3_status"] == "PENDING_VALIDATION"
    d = record["designation"]
    assert d["issuer"] == DESIGNATED_ISSUER
    assert d["audience"] == DESIGNATED_AUDIENCE
    assert DESIGNATED_JWKS in d["jwks_trust"]
    assert "Cloudflare Access" in d["ap3_enterprise_issuer"] and "Google Workspace" in d["ap3_enterprise_issuer"]
    assert "ap3-validation.ugence.ai" in d["ap3_enterprise_issuer"]
    assert TEST_GROUP in d["ap3_enterprise_issuer"] and TEST_PRINCIPAL in d["ap3_enterprise_issuer"]
    assert "accounts.google.com is the login method" in d["ap3_enterprise_issuer"]
    assert d["principal_claim"].startswith("sub")
    assert d["designated_by"] == "Rakesh Mohan" and d["designated_at"] == "2026-09-11"
    assert d["allowed_actor_type"] == "HUMAN" and d["failure_behaviour"] == "FAIL_CLOSED"
    assert d["validation_environment"] == "NON_PRODUCTION"
    # the two mappings the ratified contract cannot express for this issuer are named
    # open, not filled in with an inference
    assert d["tenant_claim"].startswith("UNRULED")
    assert d["actor_type_claim_or_mapping"].startswith("UNRULED")
    # not met: every live row is unexecuted and says so
    assert [r["result"] for r in record["validation_matrix"]] == [None] * 16
    assert record["evidence"]["ci_run_or_signed_report"] is None
    assert record["evidence"]["accepting_owner"] is None
    assert "no egress" in record["evidence"]["validation_environment_limitations"]
    assert record["evidence"]["jwks_key_identifiers"] == []


def test_the_record_and_the_egress_evidence_hold_no_secret_and_agree_on_the_host():
    text = RECORD_PATH.read_text(encoding="utf-8")
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", text)
    assert "PRIVATE KEY" not in text
    lowered = text.lower()
    for word in ("client_secret", "cf_authorization", "authorization code", "recovery code", "password"):
        assert word not in lowered, word
    assert "accounts.google.com" in text and text.count("accounts.google.com") == 1
    egress = json.loads(EGRESS_PATH.read_text(encoding="utf-8"))
    jwks = [e for e in egress["permitted_egress"] if e["purpose"].startswith("JWKS")]
    assert len(jwks) == 1 and jwks[0]["host"] == "ugence.cloudflareaccess.com"
    assert jwks[0]["scheme"] == "https" and "never disabled" in jwks[0]["verification"]


def test_the_harness_block_names_every_matrix_row_and_no_row_claims_a_live_pass():
    record = _record()
    scenarios = [r["scenario"] for r in record["validation_matrix"]]
    harness = record["conformance_harness"]
    assert harness["label"] == "IMPLEMENTATION_AND_CONFORMANCE_EVIDENCE_ONLY"
    assert [r["scenario"] for r in harness["rows"]] == scenarios
    assert all(r["live_result"] == "BLOCKED" and r["blocked_by"] for r in harness["rows"])
    assert "test_ap3_designation_conformance.py" in harness["harness"]


# --------------------------------------------------------------------------- #
# the harness: the ratified adapter and gate, configured with the designated issuer
# --------------------------------------------------------------------------- #
def _cf_claims(issuer: InProcessIssuer, **over) -> dict:
    """A payload shaped like a Cloudflare Access user token for the test principal."""
    claims = {
        "iss": issuer.issuer, "sub": "3b0f6d3e-ap3-test-uuid", "aud": [issuer.audience],
        "email": TEST_PRINCIPAL, "type": "app", "identity_nonce": "n0nce",
        "iat": int((NOW - timedelta(seconds=60)).timestamp()),
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
    }
    for key, value in over.items():
        if value is None:
            claims.pop(key, None)
        else:
            claims[key] = value
    return claims


@pytest.fixture()
def issuer():
    iss = InProcessIssuer(issuer=DESIGNATED_ISSUER, audience=DESIGNATED_AUDIENCE)
    iss.add_key("RS256", kid=KID)
    iss.start()
    try:
        yield iss
    finally:
        iss.stop()


@pytest.fixture()
def clock():
    return Clock()


def _adapter(issuer: InProcessIssuer, clock: Clock) -> JwtApproverIdentityAdapter:
    # The designated issuer and audience, exactly; the loopback JWKS stands in for the
    # designated endpoint only because this is the non-production conformance harness.
    # No tenant or actor claim is configured: neither mapping is ruled for this issuer.
    return JwtApproverIdentityAdapter(
        AdapterConfig(issuer=DESIGNATED_ISSUER, audience=DESIGNATED_AUDIENCE, jwks_url=issuer.jwks_url),
        clock=clock.datetime)


@pytest.fixture()
def gate(tmp_path, issuer, clock):
    """The plane's write gate over the real adapter, serving the implemented writes
    explicitly (the contract's default serves nothing under AP-3)."""
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    adapter = _adapter(issuer, clock)
    app = FastAPI()
    app.include_router(build_authority_reads(directory, tenant_id=TENANT, clock=clock.datetime,
                                             identity_port_configured=True))
    app.include_router(build_authority_writes(directory, tenant_id=TENANT, clock=clock.datetime,
                                              identity_port=adapter, serve=IMPLEMENTED_WRITES))
    with TestClient(app) as client:
        yield client, adapter, directory


def _load_body() -> dict:
    return {
        "principal": {"principal_id": "https%3A%2F%2Fidp.example%7Calice", "principal_kind": "HUMAN",
                      "display_ref": "alice"},
        "role": ROLE, "scope": SCOPE,
        "issued_at": (NOW - timedelta(days=1)).isoformat(),
        "expires_at": (NOW + timedelta(days=30)).isoformat(),
        "authority_reference": f"directory://roles/{ROLE}",
    }


def _write(client, proof):
    headers = {PROOF_HEADER: proof} if proof is not None else {}
    r = client.post("/authority/grants", json=_load_body(), headers=headers)
    assert proof is None or proof not in r.text, "a proof is never echoed"
    return r.status_code, r.json()


def test_the_write_gate_reads_the_ratified_proof_header_not_cloudflares():
    """AW-3: the plane reads X-Ugence-Approver-Proof. Cloudflare injects
    Cf-Access-Jwt-Assertion at the origin; admitting it is a ruling, not a default."""
    assert WRITE_PROOF_HEADER == PROOF_HEADER == "X-Ugence-Approver-Proof"


def test_row_1_a_cloudflare_shaped_token_is_refused_today_for_its_type_then_for_its_actor(gate, issuer):
    client, adapter, directory = gate
    cloudflare_typ = issuer.mint(_cf_claims(issuer), kid=KID, typ="JWT")
    answer = adapter.authenticate(cloudflare_typ)
    assert answer.authenticated is False and answer.refusal == "TYP_NOT_ACCESS_TOKEN"
    status, body = _write(client, cloudflare_typ)
    assert status != 200 and body["recorded"] is False
    # even as an at+jwt, no ruled human marker exists, so the gate refuses the actor
    access_typ = issuer.mint(_cf_claims(issuer), kid=KID)
    answer = adapter.authenticate(access_typ)
    assert answer.authenticated is True and answer.actor_type.value == "SYSTEM"
    status, body = _write(client, access_typ)
    assert status == 409 and body["result"] == "REFUSED_NOT_HUMAN"
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice",
                                as_of=NOW) == ()


def test_rows_2_and_3_wrong_issuer_and_wrong_audience_are_refused(gate, issuer):
    _client, adapter, _ = gate
    wrong_iss = issuer.mint(_cf_claims(issuer, iss="https://other.cloudflareaccess.com"), kid=KID)
    assert adapter.authenticate(wrong_iss).refusal == "ISSUER_MISMATCH"
    wrong_aud = issuer.mint(_cf_claims(issuer, aud=["0" * 64]), kid=KID)
    assert adapter.authenticate(wrong_aud).refusal == "AUDIENCE_MISMATCH"
    right_aud_in_list = issuer.mint(_cf_claims(issuer, aud=["0" * 64, DESIGNATED_AUDIENCE]), kid=KID)
    assert adapter.authenticate(right_aud_in_list).authenticated is True


def test_row_5_a_token_without_a_tenant_claim_is_refused_at_the_gate_never_filled_by_configuration(gate, issuer):
    client, adapter, _ = gate
    proof = issuer.mint(_cf_claims(issuer), kid=KID)
    assert adapter.authenticate(proof).claims.tenant_claims == ()
    status, body = _write(client, proof)
    assert status != 200 and body["recorded"] is False
    assert body["result"] in ("REFUSED_NOT_HUMAN", "REFUSED_NO_TENANT")


def test_rows_6_and_7_service_token_shape_and_missing_actor_evidence_never_become_human(gate, issuer):
    _client, adapter, _ = gate
    service_shape = issuer.mint(_cf_claims(issuer, sub="", email=None, common_name="svc-token"), kid=KID)
    assert adapter.authenticate(service_shape).refusal == "CLAIM_MALFORMED"
    no_sub = issuer.mint(_cf_claims(issuer, sub=None, common_name="svc-token"), kid=KID)
    assert adapter.authenticate(no_sub).refusal == "CLAIM_MISSING"
    unmarked = adapter.authenticate(issuer.mint(_cf_claims(issuer), kid=KID))
    assert unmarked.authenticated is True and unmarked.actor_type.value == "SYSTEM"
    # type=app is present on the human-shaped token too and decides nothing
    assert _cf_claims(issuer)["type"] == "app"


def test_row_8_expired_and_not_yet_valid_are_judged_by_the_injected_clock(gate, issuer, clock):
    _client, adapter, _ = gate
    expired = issuer.mint(_cf_claims(issuer, exp=int((NOW - timedelta(seconds=1)).timestamp())), kid=KID)
    assert adapter.authenticate(expired).refusal == "EXPIRED"
    future = issuer.mint(_cf_claims(issuer, nbf=int((NOW + timedelta(minutes=5)).timestamp())), kid=KID)
    assert adapter.authenticate(future).refusal == "NOT_YET_VALID"
    clock.advance(minutes=6)
    assert adapter.authenticate(future).authenticated is True


def test_rows_9_10_11_signature_kid_and_malformed_and_a_missing_proof(gate, issuer):
    client, adapter, _ = gate
    forged = issuer.mint(_cf_claims(issuer), kid=KID, pem=issuer.foreign_pem())
    assert adapter.authenticate(forged).refusal == "SIGNATURE_INVALID"
    fetches_before = issuer.fetches
    unknown = issuer.mint(_cf_claims(issuer), kid=KID, headers={"kid": "cf-rsa-never"})
    assert adapter.authenticate(unknown).refusal == "KEY_UNKNOWN"
    assert issuer.fetches == fetches_before + 1, "exactly one refresh on an unknown kid"
    for malformed in ("", "not-a-token", "a.b", "eyJ.eyJ.sig"):
        assert adapter.authenticate(malformed).refusal in ("MALFORMED",)
    assert adapter.authenticate(issuer.mint_unsigned(_cf_claims(issuer), kid=KID)).refusal == "ALG_NOT_PERMITTED"
    assert adapter.authenticate(issuer.mint_hmac(_cf_claims(issuer), kid=KID)).refusal == "ALG_NOT_PERMITTED"
    status, body = _write(client, None)
    assert status != 200 and body["recorded"] is False and "no proof" in body["reason"]


def test_row_12_a_jwks_outage_with_no_cached_key_is_unavailable_and_records_nothing(gate, issuer):
    client, adapter, directory = gate
    issuer.fail_next = 5
    proof = issuer.mint(_cf_claims(issuer), kid=KID)
    with pytest.raises(KeyRetrievalFailed):
        adapter.authenticate(proof)
    status, body = _write(client, proof)
    assert status != 200 and body["recorded"] is False and "could not answer" in body["reason"]
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice",
                                as_of=NOW) == ()


def test_row_13_a_rotated_key_is_accepted_after_one_refresh_and_the_withdrawn_key_is_gone(gate, issuer):
    _client, adapter, _ = gate
    assert adapter.authenticate(issuer.mint(_cf_claims(issuer), kid=KID)).authenticated is True
    new_kid = issuer.add_key("RS256", kid="cf-rsa-2")
    issuer.unpublish(KID)
    rotated = issuer.mint(_cf_claims(issuer), kid=new_kid)
    assert adapter.authenticate(rotated).authenticated is True
    assert adapter.keys.known_kids == frozenset({new_kid})
    assert adapter.authenticate(issuer.mint(_cf_claims(issuer), kid=KID)).refusal == "KEY_UNKNOWN"


def test_rows_14_to_16_cannot_run_because_no_writer_authorizer_is_composed():
    """Section 19.5 composes the AX-5 WriterAuthorizer after AP-3; the last three matrix
    rows need it. The record says NOT_RUN for all three, and this asserts the gate module
    exposes no such authorizer today rather than pretending one exists."""
    import governed_runtime_worker.authority_writes as writes

    assert not any("Authorizer" in name for name in dir(writes))
    record = _record()
    for row in record["conformance_harness"]["rows"][13:16]:
        assert row["harness_result"].startswith("NOT_RUN") and "AX-5" in row["harness_result"]


def test_the_owner_requested_rows_beyond_the_sixteen_are_recorded_truthfully(gate, issuer):
    _client, adapter, _ = gate
    record = _record()
    extra = {r["scenario"]: r["harness_result"] for r in record["conformance_harness"]["owner_requested_rows_beyond_the_sixteen"]}
    assert set(extra) == {"missing token", "missing or empty sub", "missing email", "wrong email domain",
                          "ambiguous actor type", "JWKS rotation/refetch behaviour"}
    # the adapter does not read email today: a missing or foreign-domain email changes nothing
    no_email = adapter.authenticate(issuer.mint(_cf_claims(issuer, email=None), kid=KID))
    other_domain = adapter.authenticate(issuer.mint(_cf_claims(issuer, email="someone@example.com"), kid=KID))
    assert no_email.authenticated is True and other_domain.authenticated is True
    assert extra["missing email"].startswith("NOT_A_CHECK_TODAY")
    assert extra["wrong email domain"].startswith("NOT_A_CHECK_TODAY")
    assert extra["ambiguous actor type"].startswith("REFUSED_NOT_HUMAN")


# --------------------------------------------------------------------------- #
# the probe: public-key evidence only
# --------------------------------------------------------------------------- #
def test_the_jwks_probe_reports_kids_only_and_refuses_symmetric_keys(issuer):
    import importlib.util

    spec = importlib.util.spec_from_file_location("ap3_jwks_probe", PKG / "ci" / "ap3_jwks_probe.py")
    probe = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(probe)
    assert probe.designated_url() == DESIGNATED_JWKS
    evidence = probe.probe(issuer.jwks_url)
    assert [k["kid"] for k in evidence["keys"]] == [KID]
    assert evidence["keys"][0]["kty"] == "RSA" and evidence["keys"][0]["alg"] == "RS256"
    text = json.dumps(evidence)
    for material in ("\"n\"", "\"e\"", "\"d\"", "\"k\"", "BEGIN"):
        assert material not in text, "key material is never printed"
    issuer.serve_symmetric = True
    with pytest.raises(ValueError, match="IA-2"):
        probe.probe(issuer.jwks_url)
    assert probe.main(["--url", "http://127.0.0.1:1/certs"]) == 3, "a plain-http URL is refused"
