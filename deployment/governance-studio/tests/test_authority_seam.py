"""Front-door seam 2 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-1, FD-3, FD-4, FD-6).

The P3E profile hands the Authority screen a read-only, tenant-bound view of the same
sqlite policy registry the seam-1 activation root opens, plus typed policy identities.
The failure matrix the ruling named, each a test, numbered as in the ruling.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from _activation_fixtures import make_ephemeral_signer, make_runtime_approval
from _agent_constitution_fixtures import make_constitution_policy
from ugence_agent_constitution_activation import build_activation_root
from ugence_policy_authority import (
    KeyEntitlement,
    PolicyAuthorityRequestError,
    PolicyKeyRing,
    PolicyRevocationReasonCode,
    revoke_policy,
    to_canonical_obj,
)

from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.activation import (
    AgentConstitutionArtifactCodec,
    ReadOnlyTenantBoundRegistry,
    open_studio_policy_registry,
)
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig
from governance_studio_deployment.startup_integrity import IntegrityInputs, run_startup_integrity

from conftest import basic_auth
from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, SCENARIOS_ROOT, USERNAME  # noqa: F401

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENANT = "tenant-1"
OTHER = "tenant-2"
T = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", **extra}


def _config(password_hash: str, runtime_dir, **over) -> DeploymentConfig:
    return DeploymentConfig.from_env(
        mode="test", username=USERNAME, password_hash=password_hash,
        tls_cert_file=os.path.join(CERTS, "server.crt"), tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["localhost", "127.0.0.1", "testserver"], frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST, runtime_dir=str(runtime_dir), **over,
    )


def _client(config: DeploymentConfig) -> TestClient:
    app = build_app(config, readiness=lambda: True, tracker=FailureTracker(), sleep=lambda _s: None)
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=True)


def _integrity(config: DeploymentConfig, tmp_path):
    marker = tmp_path / "frontend-build.json"
    marker.write_text(json.dumps({"version": "0.2.0", "build_hash": "x"}))
    return run_startup_integrity(IntegrityInputs(config=config, openapi_path=OPENAPI,
                                                 approved_ops_path=APPROVED_OPS,
                                                 frontend_build_marker=str(marker)))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _issuance_rows(path: str) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT count(*) FROM issuances").fetchone()[0]


@pytest.fixture()
def runtime_dir(tmp_path):
    d = tmp_path / "runtime"
    d.mkdir()
    return d


@pytest.fixture()
def registry_path(runtime_dir):
    return str(runtime_dir / "constitution-registry.sqlite3")


@pytest.fixture()
def issued(registry_path):
    """Records issued into the deployment's registry file by a test-only root with an
    ephemeral key (never the deployment's): one constitution of the displayed tenant,
    revoked, and one of another tenant. Returns their receipts and the identities."""
    registry = open_studio_policy_registry(registry_path, production_mode=False)
    signer = make_ephemeral_signer()
    revoker = make_ephemeral_signer(authority_id="ugence.policy-authority.revocation", key_id="revocation-key-1")
    ring = PolicyKeyRing([signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
                          revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,))])
    evidence, verifier = make_runtime_approval()
    root = build_activation_root(registry=registry, signer=signer, signature_verifier=ring,
                                 approval_verifier=verifier)
    ours = root.issue_constitution(policy=make_constitution_policy(tenant_id=TENANT),
                                   record_id="rec-ours", approval=evidence, issued_at=T)
    theirs = root.issue_constitution(policy=make_constitution_policy(tenant_id=OTHER),
                                     record_id="rec-theirs", approval=evidence, issued_at=T)
    revoke_policy(reference=ours.coordinate, revocation_id="revocation-ours",
                  reason_code=PolicyRevocationReasonCode.APPROVAL_WITHDRAWN, registry=registry,
                  adapters=root._adapters, signer=revoker, signature_verifier=ring,
                  revoked_at=T + timedelta(minutes=5))
    registry.close()
    c = ours.coordinate
    return {"ours": ours, "theirs": theirs, "identity": f"{c.policy_family}|{c.policy_id}|{c.scope}",
            "rows": _issuance_rows(registry_path)}


# (1) unset registry path: both reads are the typed gap, never an empty list
def test_1_unset_registry_path_is_the_typed_gap_authority_registry(config):
    with _client(config) as client:
        listed = _result(client.get("/api/v2/authority/policies", headers=_headers()))
        assert listed["available"] is False and listed["capability"] == "authority_registry"
        assert listed["result"] is None
        one = _result(client.get("/api/v2/authority/policies/rec-ours", headers=_headers()))
        assert one["available"] is False and one["capability"] == "authority_registry"


# (2) identities without the registry path: validate refuses
def test_2_identities_without_the_registry_path_are_refused(password_hash, runtime_dir):
    cfg = _config(password_hash, runtime_dir, tenant_id=TENANT, policy_identities=("f|p|s",))
    errors = [e for e in cfg.validate() if "POLICY_IDENTITIES" in e]
    assert errors and "require UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH" in errors[0]
    only_tenant = _config(password_hash, runtime_dir, tenant_id=TENANT)
    assert [e for e in only_tenant.validate() if "TENANT_ID" in e]


# (3) a malformed identity fails startup integrity before bind with a typed code
@pytest.mark.parametrize("identities,tenant", [
    (("",), TENANT), (("f|p|s", "f|p|s"), TENANT), (("f|p|ś",), TENANT), (("f|p |s",), TENANT),
    (("f|p",), TENANT), (("f||s",), TENANT), (("f|p|s",), ""), (("f|p|s",), "ten ant"), (("f|p|s",), "a|b"),
])
def test_3_a_malformed_identity_or_tenant_fails_startup_integrity_before_bind(
        password_hash, runtime_dir, registry_path, tmp_path, identities, tenant):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=tenant, policy_identities=identities)
    assert cfg.validate(), (identities, tenant)
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.code == "GOVERNANCE_STUDIO_P3E_AUTHORITY_SEAM_FAILED"
    good = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                   tenant_id=TENANT, policy_identities=("f|p|s",))
    assert good.validate() == [] and _integrity(good, tmp_path).report["authority_reads"] == "configured"


# (4) an identity with no issued record: available, empty, identities queried
def test_4_an_identity_with_no_issued_record_is_an_empty_typed_result(password_hash, runtime_dir, registry_path):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=("agent_governance.agent_constitution|nobody|global",))
    with _client(cfg) as client:
        listed = _result(client.get("/api/v2/authority/policies", headers=_headers()))
        assert listed["available"] is True and listed["result"] == []
        assert listed["identities_queried"] == [f"agent_governance.agent_constitution|nobody|global|{TENANT}"]
        assert listed["registry_kind"] == "ReadOnlyTenantBoundRegistry"


# (5) an unknown record id: available, found false
def test_5_an_unknown_record_id_is_found_false(password_hash, runtime_dir, registry_path, issued):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=(issued["identity"],))
    with _client(cfg) as client:
        one = _result(client.get("/api/v2/authority/policies/rec-unknown", headers=_headers()))
        assert one["available"] is True and one["found"] is False and one["result"] is None


# (6) a record of another tenant: typed refusal, never shown
def test_6_a_record_of_another_tenant_is_refused_and_never_displayed(password_hash, runtime_dir, registry_path, issued):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=(issued["identity"],))
    with _client(cfg) as client:
        listed = _result(client.get("/api/v2/authority/policies", headers=_headers()))
        assert [r["record_id"] for r in listed["result"]] == ["rec-ours"]
        assert all(r["coordinate"]["tenant_id"] == TENANT for r in listed["result"])
        theirs = _result(client.get("/api/v2/authority/policies/rec-theirs", headers=_headers()))
        assert theirs["found"] is False, "the other tenant's record is not reachable by id"
    registry = open_studio_policy_registry(registry_path, production_mode=False)
    view = ReadOnlyTenantBoundRegistry(registry, tenant_id=TENANT)
    c = issued["theirs"].coordinate
    with pytest.raises(PolicyAuthorityRequestError, match="cross-tenant"):
        view.issued_records_for_identity(policy_family=c.policy_family, policy_id=c.policy_id,
                                         scope=c.scope, tenant_id=OTHER)
    with pytest.raises(PolicyAuthorityRequestError, match="cross-tenant"):
        view.get_issued(c)
    with pytest.raises(PolicyAuthorityRequestError, match="cross-tenant"):
        view.revocations_for(c)
    assert view.get_issued(issued["ours"].coordinate).record_id == "rec-ours"
    registry.close()
    # through the studio, an identity naming another tenant is the typed refusal
    from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
    from ugence_governance_studio_api.settings import ApiSettings

    registry = open_studio_policy_registry(registry_path, production_mode=False)
    studio = build_studio_context(policy_registry=ReadOnlyTenantBoundRegistry(registry, tenant_id=TENANT),
                                  policy_identities=(issued["identity"] + f"|{OTHER}",))
    r = _result(TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
                .get("/api/v2/authority/policies"))
    assert r["refused"] is True and r["code"] == "authority_read_refused" and "cross-tenant" in r["reason"]
    registry.close()


# (7) revocations and supersessions are read back as stored and never written
def test_7_revocations_and_supersessions_are_read_as_stored_and_never_written(
        password_hash, runtime_dir, registry_path, issued):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=(issued["identity"],))
    with sqlite3.connect(registry_path) as conn:
        revocations_before = conn.execute("SELECT count(*) FROM revocations").fetchone()[0]
    with _client(cfg) as client:
        one = _result(client.get("/api/v2/authority/policies/rec-ours", headers=_headers()))
        (revocation,) = one["revocations"]
        assert revocation["revocation_id"] == "revocation-ours"
        assert revocation["reason_code"] == "APPROVAL_WITHDRAWN"
        assert revocation["coordinate"]["content_digest"] == issued["ours"].coordinate.content_digest
        assert "signature" not in revocation
        assert one["supersessions"] == []
    view = ReadOnlyTenantBoundRegistry(open_studio_policy_registry(registry_path, production_mode=False),
                                       tenant_id=TENANT)
    assert not any(name.startswith("append") for name in dir(view))
    with sqlite3.connect(registry_path) as conn:
        assert conn.execute("SELECT count(*) FROM revocations").fetchone()[0] == revocations_before


# (8) no issue, revoke or supersede route; issuance rows unchanged after every read
def test_8_no_mutating_route_and_the_issuance_table_is_unchanged_by_reads(
        password_hash, runtime_dir, registry_path, issued):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=(issued["identity"],))
    with _client(cfg) as client:
        for path in ("/api/v2/authority/policies", "/api/v2/authority/issue", "/api/v2/authority/revoke",
                     "/api/v2/authority/supersede", "/api/v2/authority/policies/rec-ours/revoke"):
            assert client.post(path, headers=_headers(), json={}).status_code in (404, 405), path
        client.get("/api/v2/authority/policies", headers=_headers())
        client.get("/api/v2/authority/policies/rec-ours", headers=_headers())
    assert _issuance_rows(registry_path) == issued["rows"]
    empty = str(runtime_dir / "empty.sqlite3")
    cfg2 = _config(password_hash, runtime_dir, constitution_registry_path=empty,
                   tenant_id=TENANT, policy_identities=(issued["identity"],))
    with _client(cfg2) as client:
        assert _result(client.get("/api/v2/authority/policies", headers=_headers()))["result"] == []
    assert _issuance_rows(empty) == 0


# (9) no key material or credential in source, answers or logs
def test_9_no_key_material_or_credential_in_source_answers_or_logs(
        password_hash, runtime_dir, registry_path, issued, capsys):
    src = os.path.join(HERE, "src", "governance_studio_deployment")
    for name in os.listdir(src):
        if name.endswith(".py"):
            text = open(os.path.join(src, name), encoding="utf-8").read()
            for forbidden in ("PRIVATE KEY", "Ed25519PolicySigner", "signing_key", "SigningKey(",
                              "PolicyKeyRing", "verification_key(", "revoke_policy", "append_issuance("):
                assert forbidden not in text, (name, forbidden)
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=(issued["identity"],))
    with _client(cfg) as client:
        answers = [client.get("/api/v2/authority/policies", headers=_headers()).text,
                   client.get("/api/v2/authority/policies/rec-ours", headers=_headers()).text]
    out = capsys.readouterr()
    for text in answers + [out.out, out.err]:
        assert "PRIVATE KEY" not in text and not re.search(r"-----BEGIN", text)
        assert '"signature"' not in text and '"policy":' not in text


# (10) v1, the Constitution screen and the review relay as before; the decision read keeps its gap
def test_10_v1_constitution_and_review_behave_as_before_and_the_decision_read_keeps_its_gap(
        password_hash, runtime_dir, registry_path, issued):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path,
                  tenant_id=TENANT, policy_identities=(issued["identity"],))
    with _client(cfg) as client:
        assert client.get("/api/v1/scenarios", headers=_headers()).status_code == 200
        assert client.get("/api/v2/authority/policies").status_code == 401
        valid = _result(client.post("/api/v2/constitution/validate", headers=_headers(),
                                    json={"constitution": to_canonical_obj(make_constitution_policy(), path="$")}))
        assert valid["validation_state"] == "VALID"
        review = _result(client.get("/api/v2/review/queue", headers=_headers()))
        assert review["available"] is False and review["capability"] == "review_service"
        decision = _result(client.get("/api/v2/authority/decisions/d1", headers=_headers()))
        assert decision["available"] is False and decision["capability"] == "decision_authority_store"
        assert client.get("/openapi.json", headers=_headers()).status_code == 404
    # the seam-1 root and the seam-2 view share one registry instance
    from governance_studio_deployment import app as deployment_app

    backend = deployment_app._build_backend(cfg)
    studio = backend.routes[-1].app.state.studio  # the mounted v2 app
    assert studio.authority._registry._registry is studio.constitution._root._registry


def test_the_codec_is_the_same_one_seam_1_uses():
    assert AgentConstitutionArtifactCodec().adapter_id == "ugence.agent-constitution/v1"
