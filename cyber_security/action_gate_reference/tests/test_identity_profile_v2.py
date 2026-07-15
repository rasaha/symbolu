"""Identity-profile v2 (CER V0.1): provenance-excluded action identity.

Proves the frozen-contract change is correct and non-weakening:
* v1 is unchanged (covered by the rest of the suite);
* v2 excludes only runtime/model_provider/objective from the *identity*;
* identity-bearing changes (operation, target, arguments, credential_scope,
  state binding, reversibility, policy) still change the v2 digest;
* v1 and v2 digests of the same envelope are domain-separated (never equal);
* approvals bind exactly within a profile and do NOT cross profiles.
"""
from __future__ import annotations

import copy

import pytest

from action_gate_ref import approval as approval_mod
from action_gate_ref import projection as P
from action_gate_ref.errors import ActionHashMismatchError


def _env():
    return {
        "action_id": "00000000-0000-4000-8000-000000000000",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "agent_identity": {"id": "agent:1", "key_id": "k1", "sig": "x"},
        "runtime": "ugence/1",
        "model_provider": {"model": "m", "provider": "p"},
        "delegator": {"id": "d", "type": "HUMAN"},
        "delegation_chain": [{"grant": "*"}],
        "objective": "scale web to 3",
        "tool": {"server_id": "k8s", "tool_name": "scale"},
        "operation": "DEPLOY",
        "target_resource": ["protected/web"],
        "arguments": {"replicas": "3"},
        "credential_scope": {"principal": "agent:1", "permissions": ["deploy"]},
        "current_state_hash": "sha-256:" + "ab" * 32,
        "state_freshness": {"as_of": "2026-01-01T00:00:00.000Z", "source": "k8s"},
        "policy_version": "1.0.0+abc",
        "reversibility": "REVERSIBLE",
        "correlation_id": "c1",
        "sequence_id": "1",
    }


def _with_other_provenance(env):
    e = copy.deepcopy(env)
    e["runtime"] = "langgraph/1"
    e["model_provider"] = {"model": "m2", "provider": "p2"}
    e["objective"] = "please scale the web deployment to three"
    return e


def test_v2_excludes_provenance_from_identity():
    a, b = _env(), _with_other_provenance(_env())
    assert P.action_hash(a, identity_profile="v2") == P.action_hash(b, identity_profile="v2")


def test_v1_still_includes_provenance():
    a, b = _env(), _with_other_provenance(_env())
    assert P.action_hash(a, identity_profile="v1") != P.action_hash(b, identity_profile="v1")


def test_v1_and_v2_are_domain_separated():
    e = _env()
    assert P.action_hash(e, identity_profile="v1") != P.action_hash(e, identity_profile="v2")


@pytest.mark.parametrize("mutate", [
    lambda e: e.__setitem__("operation", "DB_MUTATION"),
    lambda e: e.__setitem__("target_resource", ["protected/api"]),
    lambda e: e.__setitem__("arguments", {"replicas": "5"}),
    lambda e: e["credential_scope"].__setitem__("permissions", ["deploy", "delete"]),
    lambda e: e.__setitem__("current_state_hash", "sha-256:" + "cd" * 32),
    lambda e: e.__setitem__("reversibility", "IRREVERSIBLE"),
    lambda e: e.__setitem__("policy_version", "2.0.0+xyz"),
])
def test_v2_identity_bearing_change_alters_digest(mutate):
    base = _env()
    changed = copy.deepcopy(base)
    mutate(changed)
    assert P.action_hash(changed, identity_profile="v2") != P.action_hash(base, identity_profile="v2")


def test_v2_projection_payload_omits_only_provenance():
    payload = P.project_action_payload(_env(), identity_profile="v2")
    for k in ("runtime", "model_provider", "objective"):
        assert k not in payload
    # everything else authorization-relevant is retained
    for k in ("tool", "operation", "target_resource", "arguments", "credential_scope",
              "current_state_hash", "state_freshness", "reversibility", "policy_version"):
        assert k in payload


def test_approval_binds_within_profile_and_not_across():
    env = _env()
    ah_v2 = P.action_hash(env, identity_profile="v2")
    ap = approval_mod.build_approval(
        action_hash=ah_v2, policy_hash="ph", approver_policy="single",
        approvers=[{"id": "security-lead", "key_id": "approver:security-lead"}],
        approval_scope={"operation": "DEPLOY", "target": ["protected/web"]},
        constraints={}, issued_at="2026-01-01T00:00:00.000Z",
        expiration="2030-01-01T00:00:00.000Z", nonce="n1",
    )
    # verifies under v2 (matching profile)
    assert approval_mod.verify_approval(
        ap, env, active_policy_hash="ph", now="2026-01-01T00:00:00.000Z",
        identity_profile="v2")
    # under v1 the recomputed action_hash differs -> binding fails closed
    with pytest.raises(ActionHashMismatchError):
        approval_mod.verify_approval(
            ap, env, active_policy_hash="ph", now="2026-01-01T00:00:00.000Z",
            identity_profile="v1")
