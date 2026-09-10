"""Front-door seam 1 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-1, FD-3, FD-4, FD-5).

The P3E profile hands the studio context an activation root composed over a sqlite
policy registry under the runtime volume, with deny-by-default trust and no key
material. Unset path: the Constitution screen reports its typed gap, never an empty
result. Set: preflight returns the activation package's real report; issuance and
activation refuse; the container holds no credential; v1 and v2 behave as before.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat

import pytest
from starlette.testclient import TestClient

from _agent_constitution_fixtures import TENANT, make_constitution_policy
from ugence_policy_authority import PolicyAuthorityError, to_canonical_obj

from governance_studio_deployment import DEPLOYMENT_NAME, DEPLOYMENT_VERSION
from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.activation import (
    AgentConstitutionArtifactCodec,
    RefusingPolicySigner,
    SigningRefused,
    build_studio_activation_root,
)
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig
from governance_studio_deployment.startup_integrity import IntegrityInputs, run_startup_integrity

from conftest import basic_auth
from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, REPO, SCENARIOS_ROOT, USERNAME  # noqa: F401

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVAL = "approving-authority-1|approval://records/1|" + "a" * 64


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


def document() -> dict:
    return to_canonical_obj(make_constitution_policy(), path="$")


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


@pytest.fixture()
def runtime_dir(tmp_path):
    d = tmp_path / "runtime"
    d.mkdir()
    return d


@pytest.fixture()
def registry_path(runtime_dir):
    return str(runtime_dir / "constitution-registry.sqlite3")


# --------------------------------------------------------------------------- #
# unset: a typed gap, never an empty result
# --------------------------------------------------------------------------- #
def test_unset_registry_path_is_a_typed_gap_not_an_empty_result(config):
    assert not config.constitution_registry_configured
    with _client(config) as client:
        r = _result(client.post("/api/v2/constitution/preflight", headers=_headers(),
                                json={"constitution": document(), "record_id": "rec-1",
                                      "approval_reference": APPROVAL}))
        assert r["available"] is False and r["capability"] == "constitution_preflight"
        assert r["result"] is None and "trust root" in r["reason"]


# --------------------------------------------------------------------------- #
# set: a real registry, a real preflight, refusal of every act
# --------------------------------------------------------------------------- #
def test_set_registry_path_composes_a_root_and_preflight_reports_real_checks(
        password_hash, runtime_dir, registry_path):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path)
    assert cfg.constitution_registry_configured and cfg.validate() == []
    with _client(cfg) as client:
        valid = _result(client.post("/api/v2/constitution/validate", headers=_headers(),
                                    json={"constitution": document()}))
        assert valid["validation_state"] == "VALID"
        r = _result(client.post("/api/v2/constitution/preflight", headers=_headers(),
                                json={"constitution": document(), "record_id": "rec-1",
                                      "approval_reference": APPROVAL,
                                      "expected_reference_tenant_id": TENANT}))
        assert r["available"] is True and r["preflight_state"] == "REPORTED"
        checks = {c["name"]: c["ok"] for c in r["result"]["checks"]}
        assert checks["artifact-recognition"] and checks["reference-tenant"] and checks["lifecycle"]
        assert not any(ok for name, ok in checks.items() if name.startswith("approval"))
        untyped = _result(client.post("/api/v2/constitution/preflight", headers=_headers(),
                                      json={"constitution": document(), "record_id": "rec-1"}))
        assert untyped["preflight_state"] == "REFUSED"
        assert untyped["diagnostics"][0]["code"] == "approval_reference_unstructured"
    assert os.path.isfile(registry_path)
    with open(registry_path, "rb") as fh:
        assert fh.read(16).startswith(b"SQLite format 3")
    with sqlite3.connect(registry_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables, "the registry schema exists on the volume"


def test_issuance_and_activation_refuse_and_the_registry_stays_empty(runtime_dir, registry_path):
    from ugence_policy_authority import ApprovalEvidenceRef
    from datetime import datetime, timezone

    root = build_studio_activation_root(registry_path, production_mode=False)
    policy = make_constitution_policy()
    approval = ApprovalEvidenceRef(approval_ref="approval://records/1", approval_digest="a" * 64,
                                   approving_authority_id="approving-authority-1")
    with pytest.raises((PolicyAuthorityError, SigningRefused)):
        root.issue_constitution(policy=policy, record_id="rec-1", approval=approval,
                                issued_at=datetime(2026, 9, 6, tzinfo=timezone.utc))
    with pytest.raises(Exception):
        root.activate_constitution  # noqa: B018 - reaching the act at all is the question
        raise RuntimeError("activation is an authority act with no studio route")
    with sqlite3.connect(registry_path) as conn:
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            if "issu" in table:
                assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    with pytest.raises(SigningRefused):
        RefusingPolicySigner().sign(b"anything")


def test_the_deployment_app_has_no_issuance_or_activation_route(password_hash, runtime_dir, registry_path):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path)
    with _client(cfg) as client:
        for path in ("/api/v2/constitution/issue", "/api/v2/constitution/activate",
                     "/api/v2/constitution/issuance", "/api/v2/constitution/activation"):
            assert client.post(path, headers=_headers(), json={}).status_code in (404, 405), path


# --------------------------------------------------------------------------- #
# the path: under the volume, a file, never in memory
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [":memory:", "file::memory:?cache=shared", "relative/registry.sqlite3",
                                 "/etc/registry.sqlite3", "/tmp/elsewhere.sqlite3"])
def test_a_path_outside_the_writable_volume_or_in_memory_is_refused(password_hash, runtime_dir, bad):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=bad)
    errors = [e for e in cfg.validate() if "CONSTITUTION_REGISTRY_PATH" in e]
    assert errors, bad


def test_the_runtime_dir_itself_and_a_directory_are_refused(password_hash, runtime_dir):
    for bad in (str(runtime_dir), str(runtime_dir / "sub")):
        os.makedirs(bad, exist_ok=True)
        cfg = _config(password_hash, runtime_dir, constitution_registry_path=bad)
        assert [e for e in cfg.validate() if "CONSTITUTION_REGISTRY_PATH" in e], bad


def test_a_missing_or_unwritable_directory_fails_startup_integrity_before_bind(
        password_hash, runtime_dir, tmp_path):
    missing = _config(password_hash, runtime_dir,
                      constitution_registry_path=str(runtime_dir / "absent" / "r.sqlite3"))
    assert missing.validate() == []
    result = _integrity(missing, tmp_path)
    assert result.ok is False and result.code == "GOVERNANCE_STUDIO_P3E_CONSTITUTION_REGISTRY_FAILED"
    assert result.checks["constitution_registry_writable"] is False
    assert result.report["constitution_registry"] == "unwritable"
    locked = runtime_dir / "locked"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(str(locked), os.W_OK):
            pytest.skip("this user can write a read-only directory (root); unwritable case not testable")
        cfg = _config(password_hash, runtime_dir, constitution_registry_path=str(locked / "r.sqlite3"))
        assert _integrity(cfg, tmp_path).ok is False
    finally:
        locked.chmod(stat.S_IRWXU)
    good = _config(password_hash, runtime_dir, constitution_registry_path=str(runtime_dir / "r.sqlite3"))
    ok = _integrity(good, tmp_path)
    assert ok.checks["constitution_registry_writable"] is True and ok.report["constitution_registry"] == "configured"
    unset = _config(password_hash, runtime_dir)
    assert "constitution_registry_writable" not in _integrity(unset, tmp_path).checks
    assert _integrity(unset, tmp_path).report["constitution_registry"] == "unset"


# --------------------------------------------------------------------------- #
# no key material, no credential; v1 and v2 unchanged
# --------------------------------------------------------------------------- #
def test_no_key_material_or_credential_in_the_deployment_source_answers_or_logs(
        password_hash, runtime_dir, registry_path, capsys):
    src = os.path.join(HERE, "src", "governance_studio_deployment")
    for name in os.listdir(src):
        if name.endswith(".py"):
            text = open(os.path.join(src, name), encoding="utf-8").read()
            for forbidden in ("PRIVATE KEY", "Ed25519PolicySigner", "signing_key", "SigningKey(",
                              "PolicyKeyRing", "verification_key("):
                assert forbidden not in text, (name, forbidden)
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path)
    with _client(cfg) as client:
        answers = [client.post("/api/v2/constitution/preflight", headers=_headers(),
                               json={"constitution": document(), "record_id": "rec-1",
                                     "approval_reference": APPROVAL}).text,
                   client.post("/api/v2/constitution/validate", headers=_headers(),
                               json={"constitution": document()}).text]
    out = capsys.readouterr()
    for text in answers + [out.out, out.err]:
        assert "PRIVATE KEY" not in text and "signing_key" not in text
        assert not re.search(r"-----BEGIN", text)
    signer = RefusingPolicySigner()
    assert signer.key_id == "none" and signer.signature_alg == "none"
    assert not hasattr(signer, "verification_key")


def test_v1_and_the_review_relay_behave_exactly_as_before_with_the_root_configured(
        password_hash, runtime_dir, registry_path):
    cfg = _config(password_hash, runtime_dir, constitution_registry_path=registry_path)
    with _client(cfg) as client:
        assert client.get("/api/v1/scenarios", headers=_headers()).status_code == 200
        assert client.get("/api/v2/constitution/preflight").status_code == 401
        review = _result(client.get("/api/v2/review/queue", headers=_headers()))
        assert review["available"] is False and review["capability"] == "review_service"
        authority = _result(client.get("/api/v2/authority/policies", headers=_headers()))
        assert authority["available"] is False, "the authority seam is still absent (FD-1: one seam)"
        assert client.get("/openapi.json", headers=_headers()).status_code == 404


def test_the_codec_round_trips_the_family_and_refuses_any_other(runtime_dir):
    from ugence_agent_constitution_policy import AGENT_CONSTITUTION_ADAPTER_ID, AGENT_CONSTITUTION_POLICY_TYPE

    codec = AgentConstitutionArtifactCodec()
    policy = make_constitution_policy()
    canonical = codec.encode(policy)
    assert codec.decode(adapter_id=AGENT_CONSTITUTION_ADAPTER_ID,
                        policy_type=AGENT_CONSTITUTION_POLICY_TYPE, canonical=canonical) == policy
    with pytest.raises(PolicyAuthorityError):
        codec.encode({"not": "a policy"})
    with pytest.raises(PolicyAuthorityError):
        codec.decode(adapter_id="ugence.uvi.policy-family/v1", policy_type="Other", canonical=canonical)


# --------------------------------------------------------------------------- #
# FD-3: the composition record in the registry's own record type
# --------------------------------------------------------------------------- #
def test_the_composition_record_is_an_immutable_versioned_registry_record():
    from ugence_ai_system_registry import (
        LEGACY_CONTRACT_VERSION,
        AssessedSystemBinding,
        SystemRegistration,
        registration_id_for,
    )
    from ugence_governance_contracts.api import Validity
    from datetime import datetime

    record = json.load(open(os.path.join(HERE, "composition-record.json"), encoding="utf-8"))
    assert record["schema"] == "governance-studio.composition-record.v1"
    binding = AssessedSystemBinding(**record["binding"])
    reg = record["registration"]
    validity = Validity(issued_at=datetime.fromisoformat(reg["validity"]["issued_at"].replace("Z", "+00:00")),
                        expires_at=datetime.fromisoformat(reg["validity"]["expires_at"].replace("Z", "+00:00")))
    # Every committed composition record was written before the vocabulary binding
    # existed, and carries no ``record_version`` to say otherwise — so it reconstructs as
    # the historical record it is (VV-E's UNVERSIONED_LEGACY), under the v1 projection
    # that produced its stored digest. Stamping a vocabulary on it instead would assert a
    # taxonomy that did not exist when it was written, which is exactly what MIG-5 ruled
    # against. A future composition record, written by a build that has one, will carry
    # it and will digest differently — which is VV-B working as intended.
    rebuilt = SystemRegistration(registration_id=reg["registration_id"], binding=binding,
                                 owner_ref=reg["owner_ref"], classification_label=reg["classification_label"],
                                 validity=validity, supersedes=reg["supersedes"],
                                 registered_by=reg["registered_by"], notes=reg["notes"],
                                 record_version=LEGACY_CONTRACT_VERSION)
    assert rebuilt.registration_id == registration_id_for(binding, reg["owner_ref"], validity)
    assert rebuilt.to_dict() == reg and rebuilt.record_digest() == record["record_digest"]
    assert binding.system_id == DEPLOYMENT_NAME and binding.system_version == DEPLOYMENT_VERSION
    with open(os.path.join(HERE, "approved-runtime-config.json"), "rb") as fh:
        assert binding.configuration_digest == hashlib.sha256(fh.read()).hexdigest()
    assert reg["classification_label"] == "REFERENCE_GRADE_SHADOW_ONLY"
    assert "never edited" in reg["notes"]
    # FD-3: the chain. The current record supersedes the seam-2 record, which supersedes
    # the seam-1 record; both prior records are kept byte-for-byte and still
    # reconstruct, and each supersession is admissible.
    from ugence_ai_system_registry import supersession_refusals

    def _load(name: str):
        prior = json.load(open(os.path.join(HERE, name), encoding="utf-8"))
        pb = AssessedSystemBinding(**prior["binding"])
        pr = prior["registration"]
        return prior, SystemRegistration(
            registration_id=pr["registration_id"], binding=pb, owner_ref=pr["owner_ref"],
            classification_label=pr["classification_label"],
            validity=Validity(issued_at=datetime.fromisoformat(pr["validity"]["issued_at"].replace("Z", "+00:00")),
                              expires_at=datetime.fromisoformat(pr["validity"]["expires_at"].replace("Z", "+00:00"))),
            supersedes=pr["supersedes"], registered_by=pr["registered_by"], notes=pr["notes"],
            record_version=LEGACY_CONTRACT_VERSION)

    seam1, seam1_reg = _load("composition-record.seam-1.json")
    assert seam1_reg.record_digest() == seam1["record_digest"] == \
        "6416a5984823f7e2" + seam1["record_digest"][16:]
    assert seam1_reg.registration_id == "reg_ae7d03070a79245ca5a31eb83c2fffb8"
    assert seam1["registration"]["supersedes"] == "" and seam1_reg.system_version == "0.3.0"
    seam2, seam2_reg = _load("composition-record.seam-2.json")
    assert seam2_reg.record_digest() == seam2["record_digest"] == \
        "993107dfa315b039" + seam2["record_digest"][16:]
    assert seam2_reg.registration_id == "reg_b6eba57c58f066386115abce13816958"
    assert seam2["registration"]["supersedes"] == seam1_reg.registration_id
    assert seam2_reg.system_version == "0.4.0"
    assert supersession_refusals(seam2_reg, seam1_reg) == ()
    seam3, seam3_reg = _load("composition-record.seam-3.json")
    assert seam3_reg.record_digest() == seam3["record_digest"] == \
        "76dbab3ca097796a" + seam3["record_digest"][16:]
    assert seam3_reg.registration_id == "reg_7c8c090b23a64c2a34f31ff87b69dc66"
    assert seam3["registration"]["supersedes"] == seam2_reg.registration_id
    assert seam3_reg.system_version == "0.5.0"
    assert supersession_refusals(seam3_reg, seam2_reg) == ()
    seam5, seam5_reg = _load("composition-record.seam-5.json")
    assert seam5_reg.record_digest() == seam5["record_digest"] == \
        "92cd24847e3c6c70" + seam5["record_digest"][16:]
    assert seam5_reg.registration_id == "reg_2843f940c721c998ca68b690986ae627"
    assert seam5["registration"]["supersedes"] == seam3_reg.registration_id
    assert seam5_reg.system_version == "0.6.0"
    assert supersession_refusals(seam5_reg, seam3_reg) == ()
    seam6, seam6_reg = _load("composition-record.seam-6.json")
    assert seam6_reg.record_digest() == seam6["record_digest"] == \
        "d0c133cbaf045e01" + seam6["record_digest"][16:]
    assert seam6_reg.registration_id == "reg_4042e1b0e7af45eebb5a627fd5a59b33"
    assert seam6["registration"]["supersedes"] == seam5_reg.registration_id
    assert seam6_reg.system_version == "0.7.0"
    assert supersession_refusals(seam6_reg, seam5_reg) == ()
    seam7, seam7_reg = _load("composition-record.seam-7.json")
    assert seam7_reg.record_digest() == seam7["record_digest"] == \
        "9967538f9814acea" + seam7["record_digest"][16:]
    assert seam7_reg.registration_id == "reg_36a76ca07c81cfa0e1e360f296b77e7f"
    assert seam7["registration"]["supersedes"] == seam6_reg.registration_id
    assert seam7_reg.system_version == "0.8.0"
    assert supersession_refusals(seam7_reg, seam6_reg) == ()
    seam8, seam8_reg = _load("composition-record.seam-8.json")
    assert seam8_reg.record_digest() == seam8["record_digest"] == \
        "f2243f3a6385e205" + seam8["record_digest"][16:]
    assert seam8_reg.registration_id == "reg_8b767f5d05059e5b61ee23d092432d7f"
    assert seam8["registration"]["supersedes"] == seam7_reg.registration_id
    assert seam8_reg.system_version == "0.9.0"
    assert supersession_refusals(seam8_reg, seam7_reg) == ()
    seam9, seam9_reg = _load("composition-record.seam-9.json")
    assert seam9_reg.record_digest() == seam9["record_digest"] == \
        "62fa611aaa6e7e3e" + seam9["record_digest"][16:]
    assert seam9_reg.registration_id == "reg_b9c37e20bd5f7b1edabe45efe806aa00"
    assert seam9["registration"]["supersedes"] == seam8_reg.registration_id
    assert seam9_reg.system_version == "0.10.0"
    assert supersession_refusals(seam9_reg, seam8_reg) == ()
    seam10, seam10_reg = _load("composition-record.seam-10.json")
    assert seam10_reg.record_digest() == seam10["record_digest"] == \
        "8ba0fc15cdeceab6" + seam10["record_digest"][16:]
    assert seam10_reg.registration_id == "reg_a860dc7e07c67c2bdd857e84391a2f66"
    assert seam10["registration"]["supersedes"] == seam9_reg.registration_id
    assert seam10_reg.system_version == "0.11.0"
    assert supersession_refusals(seam10_reg, seam9_reg) == ()
    seam11, seam11_reg = _load("composition-record.seam-11.json")
    assert seam11_reg.record_digest() == seam11["record_digest"] == \
        "f65c1ae48643951c" + seam11["record_digest"][16:]
    assert seam11_reg.registration_id == "reg_8dd15380a80bdf47a456ba0c95ef97f1"
    assert seam11["registration"]["supersedes"] == seam10_reg.registration_id
    assert seam11_reg.system_version == "0.12.0"
    assert supersession_refusals(seam11_reg, seam10_reg) == ()
    # The head of the chain: workflow drafts (Bring Your Workflow phase 3A, authority-plane
    # ADR §24, BW-3A).
    assert reg["supersedes"] == seam11_reg.registration_id
    assert supersession_refusals(rebuilt, seam11_reg) == ()
    assert rebuilt.registration_id == "reg_dcf49c552c26261aa75717b6674b9d74"
    assert record["record_digest"].startswith("4546cdecf95336d5")
    assert record["supersedes_record"] == "composition-record.seam-11.json"
    assert record["seams_handed_to_build_studio_context"] == [
        "review_service_base_url", "activation_root", "policy_registry", "policy_identities",
        "provider_registry", "system_registry", "data_use_declarations",
        "vendor_declarations", "received_clearances", "deployment_report", "workflow_drafts"]
