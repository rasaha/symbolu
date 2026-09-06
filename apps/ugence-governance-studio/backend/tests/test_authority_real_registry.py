"""The Authority screen over a real policy registry (front-door seam 2, FD-6).

Records are issued by a test-only root with an ephemeral key; the studio then reads
them through the registry port as a deployment hands it: typed identities, records
displayed by their canonical references (coordinate with tenant, record id, revocation
and supersession ids), never the signature bytes or the policy body, and every
refusal typed. The studio issues, revokes and supersedes nothing.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

_TESTS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_TESTS, "..", "..", "..", ".."))
for extra in (os.path.join(_REPO, "packages", "integration", "agent-constitution-policy", "tests"),
              os.path.join(_REPO, "packages", "integration", "agent-constitution-activation", "tests"),
              os.path.join(_REPO, "packages", "policy-authority", "tests")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from _activation_fixtures import make_ephemeral_signer, make_runtime_approval  # noqa: E402
from _agent_constitution_fixtures import make_constitution_policy  # noqa: E402
from ugence_agent_constitution_activation import build_activation_root  # noqa: E402
from ugence_policy_authority import (  # noqa: E402
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyKeyRing,
    PolicyRevocationReasonCode,
    revoke_policy,
)

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app  # noqa: E402
from ugence_governance_studio_api.settings import ApiSettings  # noqa: E402
from ugence_governance_studio_api.version import API_V2_CONTRACT_VERSION  # noqa: E402

T = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def issued_registry(tenant: str = "tenant-1"):
    """A registry holding one issued constitution of ``tenant`` and its revocation."""
    registry = InMemoryPolicyRegistry()
    signer = make_ephemeral_signer()
    revoker = make_ephemeral_signer(authority_id="ugence.policy-authority.revocation", key_id="revocation-key-1")
    ring = PolicyKeyRing([signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
                          revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,))])
    evidence, verifier = make_runtime_approval()
    root = build_activation_root(registry=registry, signer=signer, signature_verifier=ring,
                                 approval_verifier=verifier)
    receipt = root.issue_constitution(policy=make_constitution_policy(tenant_id=tenant),
                                      record_id=f"rec-{tenant}", approval=evidence, issued_at=T)
    revoke_policy(reference=receipt.coordinate, revocation_id=f"revocation-{tenant}",
                  reason_code=PolicyRevocationReasonCode.APPROVAL_WITHDRAWN, registry=registry,
                  adapters=root._adapters, signer=revoker, signature_verifier=ring,
                  revoked_at=T + timedelta(minutes=5))
    return registry, receipt


def identity_of(coordinate) -> str:
    return f"{coordinate.policy_family}|{coordinate.policy_id}|{coordinate.scope}|{coordinate.tenant_id}"


def client_for(registry, identities):
    studio = build_studio_context(policy_registry=registry, policy_identities=identities)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["api_version"] == API_V2_CONTRACT_VERSION
    return body["result"]


def test_records_are_listed_by_canonical_reference_without_signature_or_body():
    registry, receipt = issued_registry()
    client = client_for(registry, (identity_of(receipt.coordinate),))
    listed = _result(client.get("/api/v2/authority/policies"))
    assert listed["available"] is True and listed["identities_queried"] == [identity_of(receipt.coordinate)]
    (record,) = listed["result"]
    assert record["record_id"] == receipt.record_id
    assert record["coordinate"]["tenant_id"] == "tenant-1"
    assert record["coordinate"]["content_digest"] == receipt.coordinate.content_digest
    assert "signature" not in record and "policy" not in record
    assert record["policy_body_digest"] == receipt.policy_body_digest


def test_one_record_is_read_by_id_with_its_revocations_and_supersessions():
    registry, receipt = issued_registry()
    client = client_for(registry, (identity_of(receipt.coordinate),))
    one = _result(client.get(f"/api/v2/authority/policies/{receipt.record_id}"))
    assert one["available"] is True and one["found"] is True
    assert one["result"]["record_id"] == receipt.record_id
    (revocation,) = one["revocations"]
    assert revocation["revocation_id"] == "revocation-tenant-1"
    assert revocation["reason_code"] == "APPROVAL_WITHDRAWN" and "signature" not in revocation
    assert revocation["coordinate"] == one["result"]["coordinate"]
    assert one["supersessions"] == []
    missing = _result(client.get("/api/v2/authority/policies/rec-unknown"))
    assert missing["available"] is True and missing["found"] is False and missing["result"] is None


def test_an_identity_with_no_issued_record_is_an_empty_typed_result():
    registry, receipt = issued_registry()
    c = receipt.coordinate
    other = f"{c.policy_family}|no-such-policy|{c.scope}|{c.tenant_id}"
    client = client_for(registry, (other,))
    listed = _result(client.get("/api/v2/authority/policies"))
    assert listed["available"] is True and listed["result"] == [] and listed["identities_queried"] == [other]


@pytest.mark.parametrize("identity", ["a|b|c", "a|b|c|d|e", "a||c|d", "", "just-a-name"])
def test_an_untyped_identity_is_a_typed_refusal_never_inferred(identity):
    registry, _receipt = issued_registry()
    client = client_for(registry, (identity,))
    for path in ("/api/v2/authority/policies", "/api/v2/authority/policies/rec-tenant-1"):
        result = _result(client.get(path))
        assert result["available"] is True and result["refused"] is True
        assert result["code"] == "policy_identity_unstructured" and result["result"] is None


def test_a_registry_refusal_is_a_typed_refusal_not_a_500():
    from ugence_policy_authority import PolicyAuthorityRequestError

    class Refusing:
        def issued_records_for_identity(self, **_kw):
            raise PolicyAuthorityRequestError("cross-tenant read refused")

    client = client_for(Refusing(), ("f|p|s|t",))
    result = _result(client.get("/api/v2/authority/policies"))
    assert result["refused"] is True and result["code"] == "authority_read_refused"
    assert "cross-tenant" in result["reason"]


def test_the_studio_never_appends_to_the_registry_and_the_decision_read_keeps_its_gap():
    registry, receipt = issued_registry()
    before = registry.snapshot() if hasattr(registry, "snapshot") else None
    client = client_for(registry, (identity_of(receipt.coordinate),))
    client.get("/api/v2/authority/policies")
    client.get(f"/api/v2/authority/policies/{receipt.record_id}")
    for path in ("/api/v2/authority/policies", "/api/v2/authority/policies/rec-tenant-1/revoke",
                 "/api/v2/authority/issue", "/api/v2/authority/supersede"):
        assert client.post(path, json={}).status_code in (404, 405), path
    assert before is None or registry.snapshot() == before
    decision = _result(client.get("/api/v2/authority/decisions/d1"))
    assert decision["available"] is False and decision["capability"] == "decision_authority_store"
