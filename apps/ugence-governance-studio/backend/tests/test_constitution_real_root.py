"""The Constitution screen over a real activation root (front-door seam 1, FD-1, FD-4, FD-5).

The root is composed exactly as a deployment composes it: the policy authority's
deny-by-default signature and approval verifiers, a signer that refuses every act and
holds no key material, and a policy registry. Preflight returns the activation
package's real report; a document that does not decode, or an approval reference that
is not fully typed, is refused with a typed diagnostic and never a 500; issuance is
unreachable through the studio.
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from starlette.testclient import TestClient

_TESTS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_TESTS, "..", "..", "..", ".."))
_FIXTURES = os.path.join(_REPO, "packages", "integration", "agent-constitution-policy", "tests")
if _FIXTURES not in sys.path:
    sys.path.insert(0, _FIXTURES)

from _agent_constitution_fixtures import CONSTITUTION_REF, TENANT, make_constitution_policy  # noqa: E402
from ugence_agent_constitution_activation import build_activation_root  # noqa: E402
from ugence_policy_authority import (  # noqa: E402
    DenyAllApprovalVerifier,
    DenyAllSignatureVerifier,
    InMemoryPolicyRegistry,
    to_canonical_obj,
)

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app  # noqa: E402
from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes  # noqa: E402
from ugence_governance_studio_api.settings import ApiSettings  # noqa: E402
from ugence_governance_studio_api.version import API_V2_CONTRACT_VERSION  # noqa: E402

DIGEST = "a" * 64  # a bare lowercase sha-256 hex digest, as ApprovalEvidenceRef requires
APPROVAL = f"approving-authority-1|approval://records/1|{DIGEST}"


class RefusingSigner:
    """The PolicySigner shape with no key: every act refuses."""

    authority_id = "unconfigured-authority"
    key_id = "no-key"
    signature_alg = "none"

    def sign(self, payload: bytes) -> bytes:
        raise RuntimeError("signing is refused: this deployment holds no key material")


def real_root():
    return build_activation_root(
        registry=InMemoryPolicyRegistry(), signer=RefusingSigner(),
        signature_verifier=DenyAllSignatureVerifier(), approval_verifier=DenyAllApprovalVerifier(),
    )


@pytest.fixture()
def client():
    studio = build_studio_context(activation_root=real_root())
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def document() -> dict:
    return to_canonical_obj(make_constitution_policy(), path="$")


def _result(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["api_version"] == API_V2_CONTRACT_VERSION
    return body["result"]


def test_a_well_formed_constitution_validates_and_a_malformed_one_is_typed_invalid(client):
    ok = _result(client.post("/api/v2/constitution/validate", json={"constitution": document()}))
    assert ok["validation_state"] == "VALID" and ok["constitution_id"] == CONSTITUTION_REF
    bad = _result(client.post("/api/v2/constitution/validate", json={"constitution": {"nonsense": True}}))
    assert bad["validation_state"] == "INVALID"
    assert bad["diagnostics"][0]["code"] == "invalid_constitution"
    assert "attribute" not in bad["diagnostics"][0]["message"]


def test_preflight_over_a_real_root_reports_the_activation_packages_own_checks(client):
    result = _result(client.post("/api/v2/constitution/preflight", json={
        "constitution": document(), "record_id": "rec-1", "approval_reference": APPROVAL,
        "expected_reference_tenant_id": TENANT,
    }))
    assert result["available"] is True and result["preflight_state"] == "REPORTED"
    checks = {c["name"]: c for c in result["result"]["checks"]}
    assert checks["artifact-recognition"]["ok"] is True
    assert checks["reference-tenant"]["ok"] is True
    assert checks["lifecycle"]["ok"] is True
    approval = [c for name, c in checks.items() if name.startswith("approval")]
    assert approval and all(c["ok"] is False for c in approval), "deny-by-default verifier: not granted"
    assert re.fullmatch(r"[0-9a-f]{64}", result["result"]["policy_body_digest"])


@pytest.mark.parametrize("reference", [None, "", "approval://records/1", "a|b", "a|b|c|d"])
def test_an_untyped_approval_reference_is_refused_never_inferred(client, reference):
    body = {"constitution": document(), "record_id": "rec-1"}
    if reference is not None:
        body["approval_reference"] = reference
    result = _result(client.post("/api/v2/constitution/preflight", json=body))
    assert result["available"] is True and result["preflight_state"] == "REFUSED"
    assert result["result"] is None
    assert result["diagnostics"][0]["code"] == "approval_reference_unstructured"


def test_a_malformed_digest_in_the_reference_and_a_malformed_document_are_typed_refusals(client):
    bad_digest = _result(client.post("/api/v2/constitution/preflight", json={
        "constitution": document(), "record_id": "rec-1",
        "approval_reference": "authority|approval://records/1|not-a-digest"}))
    assert bad_digest["preflight_state"] == "REFUSED"
    assert bad_digest["diagnostics"][0]["code"] == "approval_reference_unstructured"
    bad_doc = _result(client.post("/api/v2/constitution/preflight", json={
        "constitution": {"nonsense": True}, "record_id": "rec-1", "approval_reference": APPROVAL}))
    assert bad_doc["preflight_state"] == "REFUSED"
    assert bad_doc["diagnostics"][0]["code"] == "invalid_constitution"
    blank = _result(client.post("/api/v2/constitution/preflight", json={
        "constitution": document(), "record_id": " ", "approval_reference": APPROVAL}))
    assert blank["preflight_state"] == "REFUSED" and blank["diagnostics"][0]["code"] == "preflight_refused"


def test_issuance_and_activation_are_unreachable_and_the_registry_stays_empty(client):
    registry = InMemoryPolicyRegistry()
    root = build_activation_root(registry=registry, signer=RefusingSigner(),
                                 signature_verifier=DenyAllSignatureVerifier(),
                                 approval_verifier=DenyAllApprovalVerifier())
    c = TestClient(create_v2_app(ApiSettings(environment="test"),
                                 studio=build_studio_context(activation_root=root)))
    for path in ("/api/v2/constitution/issue", "/api/v2/constitution/activate",
                 "/api/v2/constitution/issuance", "/api/v2/constitution/activation"):
        assert c.post(path, json={}).status_code in (404, 405), path
    _result(c.post("/api/v2/constitution/preflight", json={
        "constitution": document(), "record_id": "rec-1", "approval_reference": APPROVAL}))
    assert registry.get_issued("rec-1") is None if hasattr(registry, "get_issued") else True


def test_the_v2_contract_is_unchanged_by_the_typed_service():
    with open(os.path.join(_REPO, "apps", "ugence-governance-studio", "contracts", "openapi_v2.json"), "rb") as fh:
        assert canonical_v2_openapi_bytes() == fh.read()
