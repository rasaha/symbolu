"""AP-3 designation record and its conformance harness (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
section 20; owner designation of 2026-09-11 and rulings AP3-D1 to AP3-D5, section 20.7).

    IMPLEMENTATION AND CONFORMANCE EVIDENCE ONLY. Nothing here touches the real issuer.
    Section 20 says an in-process issuer never satisfies a live row, and this module does
    not claim otherwise: rows 1 to 13 of the ``validation_matrix`` stay null until they run
    against Cloudflare. Rows 14 to 16 are the write-gate integration rows for which AP3-D5
    accepts deterministic in-process evidence, provided the real adapter boundary and the
    real write gate are exercised; the tests below are that evidence, and they say so.

The record is read from disk; every designation value asserted below is the owner's,
and the file is scanned for anything token-, secret- or key-shaped.
"""

from __future__ import annotations

import json
import pathlib
import re
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ugence_approver_identity_jwt import (
    CLOUDFLARE_ACCESS_PROFILE,
    AdapterConfig,
    JwtApproverIdentityAdapter,
)
from ugence_approver_identity_jwt.errors import KeyRetrievalFailed
from ugence_authority_directory import PrincipalKind, PrincipalRef, RoleGrant, SqliteAuthorityDirectory, grant_id_for
from ugence_governance_contracts.api import Validity
from ugence_governed_review_service.identity import PROOF_HEADER, subject_reference

from governed_runtime_worker.authority_plane import IMPLEMENTED_WRITES, WRITE_PROOF_HEADER
from governed_runtime_worker.authority_reads import build_authority_reads
from governed_runtime_worker.authority_writes import WRITE_CAPABILITIES, build_authority_writes
from governed_runtime_worker.cloudflare_access_boundary import (
    CLOUDFLARE_TRANSPORT_HEADER,
    CloudflareAccessProofBoundary,
)
from _conformance_authorizer import ConformanceDirectoryGrantAuthorizer
from _issuer import InProcessIssuer
from conftest import NOW, PKG, Clock

RECORD_PATH = PKG / "AP3_ENTERPRISE_ISSUER_VALIDATION.json"
EGRESS_PATH = PKG / "EXTERNAL_DEPLOYMENT_EVIDENCE.json"
COMPOSITION_PATH = PKG / "src" / "governed_runtime_worker" / "composition.py"

DESIGNATED_ISSUER = "https://ugence.cloudflareaccess.com"
DESIGNATED_AUDIENCE = "24b3008ed1910d53caebbaffb3358aa801bd9dc5cf9f5af8aa7ada87335b12b3"
DESIGNATED_JWKS = "https://ugence.cloudflareaccess.com/cdn-cgi/access/certs"
BOUND_TENANT = "ugence.ai"          # AP3-D2: the worker under test is the bound tenant
OTHER_TENANT = "tenant-b"
TEST_PRINCIPAL = "ap3-test@ugence.ai"
TEST_GROUP = "ugence-ap3-test@ugence.ai"
TEST_SUB = "3b0f6d3e-ap3-test-uuid"
KID = "cf-rsa-1"
ROLE = "risk-approver"
SCOPE = "approval/policy_pack"
ADMIN_SCOPE = "authority/directory"
GRANT_ROLE, REVOKE_ROLE = "authority-grant-administrator", "authority-revoke-administrator"
ROLE_FOR_CAPABILITY = {
    WRITE_CAPABILITIES["authority_grant_role"]: GRANT_ROLE,
    WRITE_CAPABILITIES["authority_revoke_grant"]: REVOKE_ROLE,
}
SCENARIOS_14_16 = ("valid identity without a directory grant", "valid identity with a wrong-tenant grant",
                   "valid identity with the correct scoped grant")


def _record() -> dict:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# the record: designated, ruled, pending, secret-free
# --------------------------------------------------------------------------- #
def test_the_record_is_designated_ruled_and_pending_not_met():
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
    # AP3-D1 to AP3-D5: the five fields are ruled, and none is UNRULED any more
    assert "UNRULED" not in json.dumps(d)
    assert d["token_type_profile"].startswith("AP3-D1") and "AMENDED 2026-09-11" in d["token_type_profile"]
    assert "typ absent" in d["token_type_profile"] and "alg exactly RS256" in d["token_type_profile"]
    assert d["tenant_claim"].startswith("AP3-D2 STATIC_ISSUER_AUDIENCE_MAPPING")
    assert f"tenant_id = '{BOUND_TENANT}'" in d["tenant_claim"] and "not the source" in d["tenant_claim"]
    assert d["actor_type_claim_or_mapping"].startswith("AP3-D3 CLAIM_SHAPE_MAPPING")
    assert "type='app'" in d["actor_type_claim_or_mapping"] and "never classifies" in d["actor_type_claim_or_mapping"]
    assert d["transport_header_boundary"].startswith("AP3-D4") and "AW-3 stands" in d["transport_header_boundary"]
    assert d["writer_authorizer_for_rows_14_to_16"].startswith("AP3-D5")
    assert "not production AX-5" in d["writer_authorizer_for_rows_14_to_16"]
    rulings = record["rulings_applied"]
    assert set(rulings) >= {"AP3-D1", "AP3-D2", "AP3-D3", "AP3-D4", "AP3-D5", "evidence_classification"}
    assert rulings["ratified_by"] == "Rakesh Mohan" and rulings["ratified_at"] == "2026-09-11"
    # not met: the thirteen live rows are unexecuted and say so; the three write-gate
    # rows carry their in-process classification and nothing more
    rows = record["validation_matrix"]
    assert len(rows) == 16
    assert all(r["evidence_class"] == "LIVE_CLOUDFLARE_EVIDENCE_REQUIRED" for n, r in enumerate(rows[:13], start=1)
               if n not in (5, 6, 7, 13))
    # rows 1 to 4 and 8 to 12 passed the owner's live cryptographic run; 5 to 7 and 13 are
    # filled under AP3-D6 from in-process evidence, 14 to 16 under AP3-D5
    passed_live = {1, 2, 3, 4, 8, 9, 10, 11, 12}
    for n, row in enumerate(rows, start=1):
        assert row["result"] == row["required"] and row["executed_at"] == "2026-09-11", n
        if n in passed_live:
            assert "ap3_live_verify.py" in row["evidence"] and row["observed"], n
        elif n <= 13:
            assert row["ruling"] == "AP3-D6" and row["evidence_class"] == "IN_PROCESS_CONFORMANCE_SUFFICIENT", n
            assert "test_ap3_designation_conformance.py::test_row" in row["evidence"], n
    assert "AP3-D6" in record["rulings_applied"] and "rows_5_to_7_and_13" in record["rulings_applied"]["evidence_classification"]
    assert d["validated_application_hostname"] == "ap3-validation-endpoint.rakeshmohan888.workers.dev"
    assert d["planned_custom_hostname"].startswith("ap3-validation.ugence.ai (planned")
    assert "not live-validated" in d["ap3_enterprise_issuer"] and "human identities" in d["production_validation_scope"]
    # the exposed token: revocation attested, not yet evidenced, so acceptance is still open
    rev = record["evidence"]["exposed_token_revocation"]
    assert rev["status"] == "OWNER_ATTESTED_NOT_YET_EVIDENCED" and rev["evidence"] is None
    assert record["evidence"]["accepting_owner_designate"].startswith("Rakesh Mohan — Founder, Ugence Labs")
    assert record["evidence"]["acceptance_report"].startswith("deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md")
    run = record["evidence"]["live_verification_runs"][0]
    assert run["summary"] == {"PASS": 9, "FAIL": 0, "BLOCKED": 4, "IN_PROCESS": 3}
    assert run["capture"]["typ"] is None and run["capture"]["signature_verified_by_the_adapter"] is True
    assert re.fullmatch(r"[0-9a-f]{64}", run["capture"]["token_sha256"]) and "never displayed" in run["capture"]["token_status"]
    assert {k for k, v in run["rows"].items() if v["status"] == "PASS"} == {str(n) for n in passed_live}
    assert [r["scenario"] for r in rows[13:]] == list(SCENARIOS_14_16)
    assert all(r["result"] == r["required"] and r["evidence_class"] == "IN_PROCESS_CONFORMANCE_SUFFICIENT"
               and "test_ap3_designation_conformance.py" in r["evidence"] for r in rows[13:])
    assert record["evidence"]["ci_run_or_signed_report"] is None
    assert record["evidence"]["accepting_owner"] is None
    assert record["evidence"]["test_timestamp"].startswith("2026-09-11T10:26:39Z")
    assert "no egress" in record["evidence"]["validation_environment_limitations"]
    # evidence item 1 is held: the owner ran the probe from a host with egress on 2026-09-11
    kids = record["evidence"]["jwks_key_identifiers"]
    assert len(kids) == 2 and all(set(k) == {"kid", "kty", "alg", "use"} for k in kids)
    assert all(k["kty"] == "RSA" and k["alg"] == "RS256" and k["use"] == "sig" for k in kids)
    assert all(re.fullmatch(r"[0-9a-f]{64}", k["kid"]) for k in kids), "a kid, never key material"
    assert re.fullmatch(r"[0-9a-f]{64}", record["evidence"]["jwks_document_sha256"])
    assert "owner" in record["evidence"]["jwks_probe_run"] and "no key material" in record["evidence"]["jwks_probe_run"]
    assert record["evidence"]["required_owner_actions"][0].startswith("DONE 2026-09-11: ci/ap3_jwks_probe.py")
    # evidence item 2 is held, redacted, and it refutes the typ expectation
    cap = record["evidence"]["live_token_capture"]
    assert cap["alg"] == "RS256" and cap["typ"] is None and cap["signature_verified"] is False
    assert cap["kid"] in {k["kid"] for k in kids} and cap["kid_matches_probed_jwks"] is True
    assert cap["iss"] == DESIGNATED_ISSUER and cap["aud"] == [DESIGNATED_AUDIENCE]
    assert cap["sub_non_empty"] is True and cap["type"] == "app" and cap["common_name_present"] is False
    assert "email" in cap["payload_keys"] and "common_name" not in cap["payload_keys"]
    assert not any("tenant" in k.lower() for k in cap["payload_keys"]), "no tenant claim exists (AP3-D2)"
    assert re.fullmatch(r"[0-9a-f]{64}", cap["token_sha256"]) and cap["token_status"].startswith("EXPOSED")
    assert any(f.startswith("AP3-D1 CONFLICT") and "AMENDED 2026-09-11" in f for f in cap["findings"])
    assert "AMENDED" in record["designation"]["token_type_profile"] and "absent" in record["designation"]["token_type_profile"]
    row1 = record["conformance_harness"]["rows"][0]
    assert row1["blocked_by"] == [] and row1["live_result"] == "PASSED_LIVE_2026-09-11"
    actions = record["evidence"]["required_owner_actions"]
    assert any(a.startswith("DONE 2026-09-11: the exposed token was revoked") for a in actions)
    assert any(a.startswith("DONE 2026-09-11: AP3-D1 amended") for a in actions)
    assert any(a.startswith("DONE 2026-09-11: ci/ap3_live_verify.py run by the owner") for a in actions)
    assert any(a.startswith("DONE 2026-09-11: AP3-D6 ruled") for a in actions)
    assert any(a.startswith("EVIDENCE the revocation") for a in actions) and any(a.startswith("ACCEPT:") for a in actions)
    assert len(record["evidence"]["required_owner_actions"]) >= 3
    assert "a test-only authorizer described as production AX-5" in record["must_never_contain"]


def test_the_record_and_the_egress_evidence_hold_no_secret_and_agree_on_the_host():
    text = RECORD_PATH.read_text(encoding="utf-8")
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", text)
    assert "PRIVATE KEY" not in text
    lowered = text.lower()
    for word in ("client_secret", "cf_authorization=", "authorization code", "recovery code", "password"):
        assert word not in lowered, word
    assert "accounts.google.com" in text and text.count("accounts.google.com") == 1
    egress = json.loads(EGRESS_PATH.read_text(encoding="utf-8"))
    jwks = [e for e in egress["permitted_egress"] if e["purpose"].startswith("JWKS")]
    assert len(jwks) == 1 and jwks[0]["host"] == "ugence.cloudflareaccess.com"
    assert jwks[0]["scheme"] == "https" and "never disabled" in jwks[0]["verification"]


def test_the_harness_block_names_every_matrix_row_and_claims_only_the_live_passes_the_owner_ran():
    record = _record()
    scenarios = [r["scenario"] for r in record["validation_matrix"]]
    harness = record["conformance_harness"]
    assert harness["label"] == "IMPLEMENTATION_AND_CONFORMANCE_EVIDENCE_ONLY"
    assert [r["scenario"] for r in harness["rows"]] == scenarios
    for n, row in enumerate(harness["rows"][:13], start=1):
        if n in {1, 2, 3, 4, 8, 9, 10, 11, 12}:
            assert row["live_result"] == "PASSED_LIVE_2026-09-11" and row["blocked_by"] == [], row["scenario"]
        else:
            assert row["live_result"] == "NOT_REQUIRED_BY_AP3-D6" and row["blocked_by"] == [], row["scenario"]
    for row in harness["rows"][13:]:
        assert row["live_result"] == "NOT_REQUIRED_BY_AP3-D5" and row["blocked_by"] == [], row["scenario"]
    assert "test_ap3_designation_conformance.py" in harness["harness"]
    assert "cloudflare-access" in harness["harness"] and "ConformanceDirectoryGrantAuthorizer" in harness["harness"]


def test_production_wiring_of_the_two_seams_is_deferred_and_the_authorizer_is_test_only():
    """AP3-D4 and AP3-D5: composition.py constructs neither the transport boundary nor
    any authorizer; the conformance authorizer lives under tests/ and names itself."""
    source = COMPOSITION_PATH.read_text(encoding="utf-8")
    for token in ("transport_boundary", "writer_authorizer", "cloudflare_access_boundary",
                  "Cf-Access-Jwt-Assertion", "Authorizer"):
        assert token not in source, token
    src_dir = PKG / "src" / "governed_runtime_worker"
    assert not any("authorizer" in p.name.lower() for p in src_dir.glob("*.py"))
    assert ConformanceDirectoryGrantAuthorizer.is_reference_authorizer is True
    assert ConformanceDirectoryGrantAuthorizer.label == "TEST_ONLY_CONFORMANCE_AUTHORIZER_NOT_AX5"
    assert pathlib.Path(__import__("_conformance_authorizer").__file__).parent == pathlib.Path(__file__).parent


# --------------------------------------------------------------------------- #
# the harness: the adapter under the ratified profile, the gate, the two seams
# --------------------------------------------------------------------------- #
def _cf_claims(issuer: InProcessIssuer, **over) -> dict:
    """A payload shaped like a Cloudflare Access user token for the test principal [I]."""
    claims = {
        "iss": issuer.issuer, "sub": TEST_SUB, "aud": [issuer.audience],
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


def _service_claims(issuer: InProcessIssuer, **over) -> dict:
    shape = dict(sub="", email=None, common_name="ap3-service-token")
    shape.update(over)
    return _cf_claims(issuer, **shape)


def _mint(issuer: InProcessIssuer, claims: dict, **kw) -> str:
    kw.setdefault("kid", KID)
    kw.setdefault("typ", "JWT")  # AP3-D1: what an Access token carries [I]
    return issuer.mint(claims, **kw)


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
    # The designated issuer and audience, exactly, under the ratified profile; the
    # loopback JWKS stands in for the designated endpoint only because this is the
    # non-production conformance harness (the profile refuses it in production).
    return JwtApproverIdentityAdapter(
        AdapterConfig(issuer=DESIGNATED_ISSUER, audience=DESIGNATED_AUDIENCE, jwks_url=issuer.jwks_url,
                      issuer_profile=CLOUDFLARE_ACCESS_PROFILE, bound_tenant=BOUND_TENANT,
                      verified_email_domain="ugence.ai"),
        clock=clock.datetime)


class Slice:
    """One composed validation slice: adapter, directory, boundary, authorizer, client."""

    def __init__(self, tmp_path, issuer, clock, *, tenant_id=BOUND_TENANT, authorizer=True, boundary=True):
        self.directory = SqliteAuthorityDirectory(str(tmp_path / f"{tenant_id}.sqlite3"))
        self.adapter = _adapter(issuer, clock)
        self.boundary = CloudflareAccessProofBoundary(self.adapter) if boundary else None
        self.authorizer = ConformanceDirectoryGrantAuthorizer(
            self.directory, clock=clock.datetime, role_for_capability=ROLE_FOR_CAPABILITY,
            scope=ADMIN_SCOPE) if authorizer else None
        self.tenant_id = tenant_id
        app = FastAPI()
        app.include_router(build_authority_reads(self.directory, tenant_id=tenant_id, clock=clock.datetime,
                                                 identity_port_configured=True))
        app.include_router(build_authority_writes(
            self.directory, tenant_id=tenant_id, clock=clock.datetime, identity_port=self.adapter,
            serve=IMPLEMENTED_WRITES, transport_boundary=self.boundary, writer_authorizer=self.authorizer))
        self.client = TestClient(app)

    def load(self, proof=None, *, cf=None, body=None):
        headers = {}
        if proof is not None:
            headers[PROOF_HEADER] = proof
        if cf is not None:
            headers[CLOUDFLARE_TRANSPORT_HEADER] = cf
        r = self.client.post("/authority/grants", json=body or _load_body(), headers=headers)
        for secret in (proof, cf):
            assert not secret or secret not in r.text, "a proof or assertion is never echoed"
        return r.status_code, r.json()

    def revoke(self, grant_id, proof=None, *, cf=None):
        headers = {}
        if proof is not None:
            headers[PROOF_HEADER] = proof
        if cf is not None:
            headers[CLOUDFLARE_TRANSPORT_HEADER] = cf
        r = self.client.post(f"/authority/grants/{grant_id}/revoke", json={"reason": "conformance"}, headers=headers)
        for secret in (proof, cf):
            assert not secret or secret not in r.text
        return r.status_code, r.json()

    def hold(self, role: str, *, tenant_id=None, principal_id=None) -> RoleGrant:
        """Load, directly into the directory, an active grant for the test principal."""
        tenant_id = tenant_id or self.tenant_id
        principal_id = principal_id or self.subject_reference()
        principal = PrincipalRef(principal_id=principal_id, principal_kind=PrincipalKind.HUMAN,
                                 display_ref=TEST_PRINCIPAL)
        validity = Validity(issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30))
        grant = RoleGrant(grant_id=grant_id_for(tenant_id, principal_id, role, ADMIN_SCOPE, validity),
                          tenant_id=tenant_id, principal=principal, role=role, scope=ADMIN_SCOPE,
                          validity=validity, authority_reference="directory://conformance")
        return self.directory.put_grant(grant, as_of=NOW, loaded_by="conformance-setup")

    def subject_reference(self) -> str:
        return f"https%3A%2F%2Fugence.cloudflareaccess.com|{TEST_SUB}"


@pytest.fixture()
def slice_(tmp_path, issuer, clock):
    return Slice(tmp_path, issuer, clock)


def _load_body() -> dict:
    return {
        "principal": {"principal_id": "https%3A%2F%2Fidp.example%7Calice", "principal_kind": "HUMAN",
                      "display_ref": "alice"},
        "role": ROLE, "scope": SCOPE,
        "issued_at": (NOW - timedelta(days=1)).isoformat(),
        "expires_at": (NOW + timedelta(days=30)).isoformat(),
        "authority_reference": f"directory://roles/{ROLE}",
    }


def test_the_write_gate_reads_the_ratified_proof_header_and_the_boundary_reads_cloudflares():
    """AW-3 stands (AP3-D4): the plane's proof header is unchanged; the transport header
    belongs to the boundary and to nothing else."""
    assert WRITE_PROOF_HEADER == PROOF_HEADER == "X-Ugence-Approver-Proof"
    assert CLOUDFLARE_TRANSPORT_HEADER == "Cf-Access-Jwt-Assertion"
    assert CloudflareAccessProofBoundary.header != PROOF_HEADER


def test_row_1_a_cloudflare_shaped_token_is_accepted_under_the_profile_over_both_channels(slice_, issuer):
    """Row 1 through the whole slice: adapter, gate, boundary and the authorizer."""
    s = slice_
    token = _mint(issuer, _cf_claims(issuer))
    answer = s.adapter.authenticate(token)
    assert answer.authenticated and answer.actor_type.value == "HUMAN"
    assert answer.claims.tenant_claims == (BOUND_TENANT,)
    assert answer.actor_id == subject_reference(answer.claims) == s.subject_reference()
    assert answer.issuer_profile == CLOUDFLARE_ACCESS_PROFILE
    # with the grant-role capability held, the load is RECORDED over the plane's header
    s.hold(GRANT_ROLE)
    status, body = s.load(token)
    assert status == 200 and body["result"] == "RECORDED" and body["identity_proof"] == "IDP_AUTHENTICATED"
    assert body["subject"] == s.subject_reference() and body["proof_channel"] == PROOF_HEADER
    assert body["issuer_validation"] == "IN_PROCESS_ISSUER_ONLY", "nothing here claims enterprise validation"
    # and over Cloudflare's transport header, through the boundary (an identical load replays)
    status, body = s.load(cf=token)
    assert status == 409 and body["result"] == "ALREADY_LOADED", "same identity, same grant, replayed"
    other = dict(_load_body(), role="second-role")
    status, body = s.load(cf=token, body=other)
    assert status == 200 and body["result"] == "RECORDED" and body["proof_channel"] == CLOUDFLARE_TRANSPORT_HEADER
    assert body["subject"] == s.subject_reference()
    # the at+jwt shape is refused under this profile; the rfc9068 profile is untouched
    assert s.adapter.authenticate(_mint(issuer, _cf_claims(issuer), typ="at+jwt")).refusal == "TYP_NOT_PROFILE_TYPE"


def test_the_identity_stage_alone_records_when_no_authorizer_is_composed(tmp_path, issuer, clock):
    """What the composed worker's gate does today (no authorizer, no boundary) with a
    profile-configured adapter: the AW-5 gate, and nothing about authority."""
    s = Slice(tmp_path, issuer, clock, authorizer=False, boundary=False)
    token = _mint(issuer, _cf_claims(issuer))
    status, body = s.load(token)
    assert status == 200 and body["result"] == "RECORDED" and "authorization" not in body
    # without the boundary, Cloudflare's header alone is no proof at all
    status, body = s.load(cf=token, body=dict(_load_body(), role="x"))
    assert status == 409 and body["result"] == "REFUSED_UNAUTHENTICATED" and PROOF_HEADER in body["reason"]


def test_the_live_header_shape_is_admitted_under_ap3_d1_as_amended_and_relaxes_nothing_else(slice_, issuer):
    """evidence.live_token_capture (2026-09-11): the real Access token carries alg RS256,
    a kid and no typ. AP3-D1 as amended admits the absent typ under this profile only;
    a present typ must be JWT, alg must be RS256, and the signature path is unchanged."""
    import jwt as pyjwt

    live_shape = _mint(issuer, _cf_claims(issuer, nbf=int((NOW - timedelta(seconds=60)).timestamp()),
                                          country="IN", policy_id="p", h_INTERNAL_DO_NOT_USE="x"),
                       typ=None, headers={"typ": None})
    assert "typ" not in pyjwt.get_unverified_header(live_shape)
    answer = slice_.adapter.authenticate(live_shape)
    assert answer.authenticated and answer.actor_type.value == "HUMAN" and answer.claims.tenant_claims == (BOUND_TENANT,)
    slice_.hold(GRANT_ROLE)
    status, body = slice_.load(cf=live_shape)
    assert status == 200 and body["result"] == "RECORDED" and body["proof_channel"] == CLOUDFLARE_TRANSPORT_HEADER
    # nothing else relaxed
    assert slice_.adapter.authenticate(_mint(issuer, _cf_claims(issuer), typ="at+jwt")).refusal == "TYP_NOT_PROFILE_TYPE"
    es_kid = issuer.add_key("ES256", kid="cf-es-1")
    assert slice_.adapter.authenticate(_mint(issuer, _cf_claims(issuer), kid=es_kid, typ=None,
                                             headers={"typ": None})).refusal == "ALG_NOT_PERMITTED"
    assert slice_.adapter.authenticate(_mint(issuer, _cf_claims(issuer), typ=None, headers={"typ": None},
                                             pem=issuer.foreign_pem())).refusal == "SIGNATURE_INVALID"
    assert slice_.adapter.authenticate(_mint(issuer, _cf_claims(issuer), typ=None,
                                             headers={"typ": None, "kid": "cf-rsa-never"})).refusal == "KEY_UNKNOWN"
    assert slice_.adapter.authenticate(issuer.mint_unsigned(_cf_claims(issuer), kid=KID, typ="JWT")).refusal \
        == "ALG_NOT_PERMITTED"


def test_rows_2_and_3_wrong_issuer_and_wrong_audience_are_refused(slice_, issuer):
    adapter = slice_.adapter
    wrong_iss = _mint(issuer, _cf_claims(issuer, iss="https://other.cloudflareaccess.com"))
    assert adapter.authenticate(wrong_iss).refusal == "ISSUER_MISMATCH"
    wrong_aud = _mint(issuer, _cf_claims(issuer, aud=["0" * 64]))
    assert adapter.authenticate(wrong_aud).refusal == "AUDIENCE_MISMATCH"
    right_aud_in_list = _mint(issuer, _cf_claims(issuer, aud=["0" * 64, DESIGNATED_AUDIENCE]))
    assert adapter.authenticate(right_aud_in_list).authenticated is True
    for token in (wrong_iss, wrong_aud):
        status, body = slice_.load(token)
        assert status == 409 and body["result"] == "REFUSED_UNAUTHENTICATED"


def test_row_4_a_wrong_tenant_is_refused_at_the_adapter_and_at_a_foreign_gate(tmp_path, slice_, issuer, clock):
    adapter = slice_.adapter
    foreign = _mint(issuer, _cf_claims(issuer, email="someone@example.com"))
    assert adapter.authenticate(foreign).refusal == "EMAIL_DOMAIN_MISMATCH"
    status, body = slice_.load(foreign)
    assert status == 409 and body["result"] == "REFUSED_UNAUTHENTICATED"
    lookalike = _mint(issuer, _cf_claims(issuer, email="ap3-test@ugence.ai.example.com"))
    assert adapter.authenticate(lookalike).refusal == "EMAIL_DOMAIN_MISMATCH"
    # a gate for another tenant refuses a correctly bound identity
    other = Slice(tmp_path, issuer, clock, tenant_id=OTHER_TENANT)
    status, body = other.load(_mint(issuer, _cf_claims(issuer)))
    assert status == 409 and body["result"] == "REFUSED_TENANT_MISMATCH"


def test_row_5_no_tenant_claim_exists_and_configuration_never_fills_the_gap(slice_, issuer):
    adapter = slice_.adapter
    decoy = adapter.authenticate(_mint(issuer, _cf_claims(issuer, ugence_tenant="tenant-z")))
    assert decoy.claims.tenant_claims == (BOUND_TENANT,), "a top-level claim is never read"
    uncorroborated = adapter.authenticate(_mint(issuer, _cf_claims(issuer, email=None)))
    assert uncorroborated.refusal == "ACTOR_SHAPE_AMBIGUOUS"
    service = adapter.authenticate(_mint(issuer, _service_claims(issuer)))
    assert service.authenticated and service.claims.tenant_claims == ()
    status, body = slice_.load(_mint(issuer, _service_claims(issuer)))
    assert status == 409 and body["result"] == "REFUSED_NOT_HUMAN"


def test_rows_6_and_7_service_token_shape_and_missing_actor_evidence_never_become_human(slice_, issuer):
    adapter = slice_.adapter
    service = adapter.authenticate(_mint(issuer, _service_claims(issuer)))
    assert service.authenticated and service.actor_type.value == "SYSTEM" and service.claims.subject == "ap3-service-token"
    absent_sub = adapter.authenticate(_mint(issuer, _service_claims(issuer, sub=None)))
    assert absent_sub.actor_type.value == "SYSTEM"
    for mixed in (_service_claims(issuer, email=TEST_PRINCIPAL),          # service token with an email
                  _cf_claims(issuer, common_name="svc"),                  # human sub with a service marker
                  _cf_claims(issuer, email=None),                         # sub without email
                  _cf_claims(issuer, sub=""),                             # email without sub
                  _cf_claims(issuer, sub="", email=None)):                # neither
        assert adapter.authenticate(_mint(issuer, mixed)).refusal == "ACTOR_SHAPE_AMBIGUOUS", mixed
    promoted = adapter.authenticate(_mint(issuer, _service_claims(issuer, ugence_actor="human-sign-in")))
    assert promoted.actor_type.value == "SYSTEM"
    for type_value in ("app", "org", None):
        assert adapter.authenticate(_mint(issuer, _cf_claims(issuer, type=type_value))).actor_type.value == "HUMAN"
        assert adapter.authenticate(_mint(issuer, _service_claims(issuer, type=type_value))).actor_type.value == "SYSTEM"
    status, body = slice_.load(_mint(issuer, _service_claims(issuer)))
    assert status == 409 and body["result"] == "REFUSED_NOT_HUMAN"


def test_row_8_expired_and_not_yet_valid_are_judged_by_the_injected_clock(slice_, issuer, clock):
    adapter = slice_.adapter
    expired = _mint(issuer, _cf_claims(issuer, exp=int((NOW - timedelta(seconds=1)).timestamp())))
    assert adapter.authenticate(expired).refusal == "EXPIRED"
    future = _mint(issuer, _cf_claims(issuer, nbf=int((NOW + timedelta(minutes=5)).timestamp())))
    assert adapter.authenticate(future).refusal == "NOT_YET_VALID"
    clock.advance(minutes=6)
    assert adapter.authenticate(future).authenticated is True


def test_rows_9_10_11_signature_kid_malformed_and_a_missing_proof(slice_, issuer):
    adapter = slice_.adapter
    forged = _mint(issuer, _cf_claims(issuer), pem=issuer.foreign_pem())
    assert adapter.authenticate(forged).refusal == "SIGNATURE_INVALID"
    fetches_before = issuer.fetches
    unknown = _mint(issuer, _cf_claims(issuer), headers={"kid": "cf-rsa-never"})
    assert adapter.authenticate(unknown).refusal == "KEY_UNKNOWN"
    assert issuer.fetches == fetches_before + 1, "exactly one refresh on an unknown kid"
    for malformed in ("", "not-a-token", "a.b", "eyJ.eyJ.sig"):
        assert adapter.authenticate(malformed).refusal == "MALFORMED"
    assert adapter.authenticate(issuer.mint_unsigned(_cf_claims(issuer), kid=KID, typ="JWT")).refusal == "ALG_NOT_PERMITTED"
    assert adapter.authenticate(issuer.mint_hmac(_cf_claims(issuer), kid=KID, typ="JWT")).refusal == "ALG_NOT_PERMITTED"
    assert adapter.authenticate(_mint(issuer, _cf_claims(issuer), typ="at+jwt")).refusal == "TYP_NOT_PROFILE_TYPE"
    status, body = slice_.load(None)
    assert status == 409 and body["result"] == "REFUSED_UNAUTHENTICATED" and "no proof" in body["reason"]
    # a garbage or forged assertion on Cloudflare's header is refused through the boundary
    for bad in ("not-a-token", forged, unknown):
        status, body = slice_.load(cf=bad)
        assert status == 409 and body["result"] == "REFUSED_UNAUTHENTICATED", bad[:10]


def test_row_12_a_jwks_outage_with_no_cached_key_is_unavailable_and_records_nothing(slice_, issuer):
    issuer.fail_next = 5
    proof = _mint(issuer, _cf_claims(issuer))
    with pytest.raises(KeyRetrievalFailed):
        slice_.adapter.authenticate(proof)
    status, body = slice_.load(proof)
    assert status == 409 and body["result"] == "REFUSED_IDENTITY_UNAVAILABLE" and "could not answer" in body["reason"]
    status, body = slice_.load(cf=proof)
    assert status == 409 and body["result"] == "REFUSED_IDENTITY_UNAVAILABLE"
    assert slice_.directory.grants_for(tenant_id=BOUND_TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice",
                                       as_of=NOW) == ()


def test_row_13_a_rotated_key_is_accepted_after_one_refresh_and_the_withdrawn_key_is_gone(slice_, issuer):
    adapter = slice_.adapter
    assert adapter.authenticate(_mint(issuer, _cf_claims(issuer))).authenticated is True
    new_kid = issuer.add_key("RS256", kid="cf-rsa-2")
    issuer.unpublish(KID)
    rotated = _mint(issuer, _cf_claims(issuer), kid=new_kid)
    assert adapter.authenticate(rotated).authenticated is True
    assert adapter.keys.known_kids == frozenset({new_kid})
    assert adapter.authenticate(_mint(issuer, _cf_claims(issuer))).refusal == "KEY_UNKNOWN"


# --------------------------------------------------------------------------- #
# rows 14 to 16 (AP3-D5): the real adapter, the real gate, a test-only authorizer
# --------------------------------------------------------------------------- #
def test_row_14_a_valid_identity_without_a_directory_grant_is_authenticated_but_unauthorized(slice_, issuer):
    token = _mint(issuer, _cf_claims(issuer))
    assert slice_.adapter.authenticate(token).authenticated is True
    for kwargs in (dict(proof=token), dict(cf=token)):
        status, body = slice_.load(**kwargs)
        assert status == 403 and body["result"] == "REFUSED_UNAUTHORIZED" and body["ruling"] == "AX-5"
        assert body["recorded"] is False and body["subject"] == slice_.subject_reference()
        assert body["capability"] == WRITE_CAPABILITIES["authority_grant_role"]
        assert "no active directory grant" in body["reason"]
    assert slice_.directory.grants_for(tenant_id=BOUND_TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice",
                                       as_of=NOW) == ()
    call = slice_.authorizer.calls[-1]
    assert call == {"principal_id": slice_.subject_reference(), "tenant_id": BOUND_TENANT,
                    "operation": "authority_grant_role", "capability": WRITE_CAPABILITIES["authority_grant_role"]}


def test_row_15_a_wrong_tenant_grant_is_unauthorized(tmp_path, slice_, issuer, clock):
    token = _mint(issuer, _cf_claims(issuer))
    slice_.hold(GRANT_ROLE, tenant_id=OTHER_TENANT)            # the right role, the wrong tenant
    status, body = slice_.load(token)
    assert status == 403 and body["result"] == "REFUSED_UNAUTHORIZED"
    assert f"tenant {BOUND_TENANT!r}" in body["reason"]
    # a gate for the other tenant refuses the identity before any authorizer is asked
    other = Slice(tmp_path, issuer, clock, tenant_id=OTHER_TENANT)
    other.hold(GRANT_ROLE)
    status, body = other.load(token)
    assert status == 409 and body["result"] == "REFUSED_TENANT_MISMATCH" and other.authorizer.calls == []


def test_row_16_the_correct_scoped_grant_permits_only_the_named_capability(slice_, issuer):
    token = _mint(issuer, _cf_claims(issuer))
    slice_.hold(GRANT_ROLE)
    status, body = slice_.load(token)
    assert status == 200 and body["result"] == "RECORDED"
    assert body["authorization"] == {"ruling": "AX-5", "capability": WRITE_CAPABILITIES["authority_grant_role"],
                                     "authorizer_is_reference": True}
    loaded = body["grant"]["grant_id"]
    # the same identity, the same grant-role capability, cannot revoke: a different capability
    status, body = slice_.revoke(loaded, token)
    assert status == 403 and body["result"] == "REFUSED_UNAUTHORIZED"
    assert body["capability"] == WRITE_CAPABILITIES["authority_revoke_grant"]
    assert slice_.directory.get_grant(loaded).revoked_at is None
    # a wrong-scope grant of the revoke role does not count either
    slice_.hold(REVOKE_ROLE, tenant_id=OTHER_TENANT)
    status, body = slice_.revoke(loaded, cf=token)
    assert status == 403
    # the exact revoke grant does, over the transport channel too
    slice_.hold(REVOKE_ROLE)
    status, body = slice_.revoke(loaded, cf=token)
    assert status == 200 and body["result"] == "RECORDED" and body["event"] == "REVOKED"
    assert body["proof_channel"] == CLOUDFLARE_TRANSPORT_HEADER
    assert body["authorization"]["capability"] == WRITE_CAPABILITIES["authority_revoke_grant"]


def test_the_seams_fail_closed_at_construction_and_the_boundary_never_leaks(tmp_path, issuer, clock):
    adapter = _adapter(issuer, clock)
    directory = SqliteAuthorityDirectory(str(tmp_path / "x.sqlite3"))
    authorizer = ConformanceDirectoryGrantAuthorizer(directory, clock=clock.datetime,
                                                     role_for_capability=ROLE_FOR_CAPABILITY, scope=ADMIN_SCOPE)
    with pytest.raises(ValueError, match="refused in production"):
        build_authority_writes(directory, tenant_id=BOUND_TENANT, clock=clock.datetime, identity_port=adapter,
                               serve=IMPLEMENTED_WRITES, writer_authorizer=authorizer, production=True)
    with pytest.raises(ValueError, match="WriterAuthorizer seam"):
        build_authority_writes(directory, tenant_id=BOUND_TENANT, clock=clock.datetime, identity_port=adapter,
                               writer_authorizer=object())
    with pytest.raises(ValueError, match="without an identity port"):
        build_authority_writes(directory, tenant_id=BOUND_TENANT, clock=clock.datetime, identity_port=None,
                               transport_boundary=CloudflareAccessProofBoundary(adapter))
    rfc = JwtApproverIdentityAdapter(
        AdapterConfig(issuer="https://issuer.test", audience="aud", jwks_url=issuer.jwks_url), clock=clock.datetime)
    with pytest.raises(ValueError, match="cloudflare-access issuer profile"):
        CloudflareAccessProofBoundary(rfc)
    boundary = CloudflareAccessProofBoundary(adapter)
    assert boundary.issuer == DESIGNATED_ISSUER and boundary.presented({}) is False
    with pytest.raises(ValueError):
        boundary.identity_from({})
    token = _mint(issuer, _cf_claims(issuer))
    identity = boundary.identity_from({CLOUDFLARE_TRANSPORT_HEADER: token})
    assert identity.authenticated and all(part not in repr(identity) for part in token.split("."))
    # an authorizer that cannot answer is a refusal, not a pass
    class Broken:
        is_reference_authorizer = True

        def authorize(self, **_kw):
            raise RuntimeError("down")

    app = FastAPI()
    app.include_router(build_authority_writes(directory, tenant_id=BOUND_TENANT, clock=clock.datetime,
                                              identity_port=adapter, serve=IMPLEMENTED_WRITES,
                                              writer_authorizer=Broken()))
    r = TestClient(app).post("/authority/grants", json=_load_body(), headers={PROOF_HEADER: token})
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_AUTHORIZER_UNAVAILABLE"


def test_the_owner_requested_rows_beyond_the_sixteen_are_recorded_truthfully(slice_, issuer):
    adapter = slice_.adapter
    record = _record()
    extra = {r["scenario"]: r["harness_result"] for r in record["conformance_harness"]["owner_requested_rows_beyond_the_sixteen"]}
    assert set(extra) == {"missing token", "missing or empty sub", "missing email", "wrong email domain",
                          "ambiguous actor type", "JWKS rotation/refetch behaviour"}
    assert adapter.authenticate(_mint(issuer, _cf_claims(issuer, email=None))).refusal == "ACTOR_SHAPE_AMBIGUOUS"
    assert adapter.authenticate(_mint(issuer, _cf_claims(issuer, sub=""))).refusal == "ACTOR_SHAPE_AMBIGUOUS"
    assert adapter.authenticate(_mint(issuer, _cf_claims(issuer, email="someone@example.com"))).refusal \
        == "EMAIL_DOMAIN_MISMATCH"
    assert extra["missing email"].startswith("REFUSED_ACTOR_SHAPE_AMBIGUOUS")
    assert extra["missing or empty sub"].startswith("REFUSED_ACTOR_SHAPE_AMBIGUOUS")
    assert extra["wrong email domain"].startswith("REFUSED_EMAIL_DOMAIN_MISMATCH")
    assert extra["ambiguous actor type"].startswith("REFUSED_ACTOR_SHAPE_AMBIGUOUS")
    assert extra["missing token"].startswith("REFUSED_UNAUTHENTICATED")


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


def test_the_token_capture_prints_only_the_redacted_fields_and_never_the_token(issuer, clock):
    import importlib.util
    import subprocess
    import sys

    spec = importlib.util.spec_from_file_location("ap3_token_capture", PKG / "ci" / "ap3_token_capture.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    token = _mint(issuer, _cf_claims(issuer))
    out = module.capture(token)
    assert tuple(out) == module.CAPTURE_FIELDS
    assert out["alg"] == "RS256" and out["typ"] == "JWT" and out["kid"] == KID
    assert out["payload_keys"] == sorted(_cf_claims(issuer))
    assert out["iss"] == DESIGNATED_ISSUER and out["aud"] == [DESIGNATED_AUDIENCE]
    assert out["sub_non_empty"] is True and out["type"] == "app" and out["signature_verified"] is False
    text = json.dumps(out)
    for part in token.split("."):
        assert part not in text
    for secret in (TEST_SUB, TEST_PRINCIPAL, "n0nce"):
        assert secret not in text
    assert module.capture(_mint(issuer, _service_claims(issuer)))["sub_non_empty"] is False
    with pytest.raises(ValueError):
        module.capture("not-a-token")
    # the CLI reads stdin only and its stdout carries no token segment either
    run = subprocess.run([sys.executable, str(PKG / "ci" / "ap3_token_capture.py")], input=token + "\n",
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0 and '"outcome": "REDACTED_CAPTURE"' in run.stdout
    assert all(part not in run.stdout + run.stderr for part in token.split("."))
    bad = subprocess.run([sys.executable, str(PKG / "ci" / "ap3_token_capture.py")], input="garbage",
                         capture_output=True, text=True, check=False)
    assert bad.returncode == 3 and "garbage" not in bad.stdout + bad.stderr


def test_the_live_verifier_drives_the_rows_a_login_can_drive_and_never_prints_the_token(issuer, monkeypatch, capsys):
    """ci/ap3_live_verify.py over the in-process issuer (loopback JWKS, the designated
    issuer and audience): rows 1 to 4 and 8 to 12 PASS with a genuinely verified token,
    5 to 7 and 13 are BLOCKED, 14 to 16 are IN_PROCESS, and no token segment is printed."""
    import io
    import importlib.util
    from datetime import datetime, timezone

    spec = importlib.util.spec_from_file_location("ap3_live_verify", PKG / "ci" / "ap3_live_verify.py")
    verify = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verify)
    now = datetime.now(timezone.utc)
    claims = _cf_claims(issuer, iat=int((now - timedelta(seconds=60)).timestamp()),
                        nbf=int((now - timedelta(seconds=60)).timestamp()),
                        exp=int((now + timedelta(hours=1)).timestamp()), country="IN", policy_id="p")
    token = _mint(issuer, claims, typ=None, headers={"typ": None})
    monkeypatch.setattr("sys.stdin", io.StringIO(token + "\n"))
    code = verify.main(["--token-stdin", "--jwks-url", issuer.jwks_url,
                        "--unavailable-jwks-url", "http://127.0.0.1:1/certs"])
    out = capsys.readouterr().out
    assert code == 0, out
    for part in token.split("."):
        assert part not in out
    assert TEST_PRINCIPAL not in out and TEST_SUB not in out
    result = json.loads(out)
    assert result["outcome"] == "LIVE_VERIFICATION" and result["capture"]["typ"] is None
    assert result["capture"]["kid"] == KID and result["jwks_kids_seen"] == [KID]
    status = {r["row"]: r["status"] for r in result["rows"]}
    assert [r["row"] for r in result["rows"]] == list(range(1, 17))
    assert {n for n, s in status.items() if s == "PASS"} == {1, 2, 3, 4, 8, 9, 10, 11, 12}
    assert {n for n, s in status.items() if s == "BLOCKED"} == {5, 6, 7, 13}
    assert {n for n, s in status.items() if s == "IN_PROCESS"} == {14, 15, 16}
    assert result["summary"] == {"PASS": 9, "FAIL": 0, "BLOCKED": 4, "IN_PROCESS": 3}
    assert "declares nothing MET" in result["claims"]
    # the login filter drops any token-shaped line
    assert verify.filtered_lines("Successfully fetched your token:\n" + token + "\nbye") == [
        "Successfully fetched your token:", "(a line carrying a token was suppressed)", "bye"]
    # a tampered token fails row 9's expectation the other way round: FAIL is reported, never hidden
    monkeypatch.setattr("sys.stdin", io.StringIO(verify.tamper_signature(token)))
    code = verify.main(["--token-stdin", "--jwks-url", issuer.jwks_url,
                        "--unavailable-jwks-url", "http://127.0.0.1:1/certs"])
    out = capsys.readouterr().out
    assert code == 1 and json.loads(out)["rows"][0]["status"] == "FAIL"


def test_the_acceptance_report_is_rendered_from_the_record_and_is_not_accepted():
    """The canonical acceptance artifact is AP3_ACCEPTANCE_REPORT.md, rendered by
    ci/ap3_acceptance_report.py from the record; it may not drift, and while the record's
    accepting_owner is null it says NOT ACCEPTED and carries the statement to be issued."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("ap3_acceptance_report", PKG / "ci" / "ap3_acceptance_report.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    record = _record()
    rendered = mod.render(record)
    committed = (PKG / "AP3_ACCEPTANCE_REPORT.md").read_text(encoding="utf-8")
    assert committed == rendered, "re-render with: python ci/ap3_acceptance_report.py --write"
    assert mod.ACCEPTOR == "Rakesh Mohan — Founder, Ugence Labs"
    assert "**Status:** `PENDING_VALIDATION`" in committed and "**Accepted:** NOT ACCEPTED" in committed
    assert "I, Rakesh Mohan, Founder, Ugence Labs, accept" in committed
    assert committed.count("| `") >= 16 and "`null`" not in committed, "every row carries a result"
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", committed)
    assert mod.main(["--check"]) == 0
