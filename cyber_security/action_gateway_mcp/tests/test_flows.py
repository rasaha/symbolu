"""Phase separation, simulation binding, approval binding, constraints."""

from __future__ import annotations

import copy

import pytest

from action_gateway_mcp._core import ref_projection
from tests.helpers import approved_terraform, backup, make


def test_prepare_does_not_execute_or_mint_token():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": "w"})
    assert p["phase"] == "prepared" and p["execution_token"] is None
    rec = mcp.gateway.records[p["request_id"]]
    assert rec.token is None and rec.decision is None  # not yet evaluated


def test_evaluation_does_not_execute():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "filesystem.write", {"path": "a", "content": "b"})
    r = mcp.evaluate(cs.context(), p["request_id"])
    assert r["executable"] is False  # needs simulation first
    assert mcp.gateway.records[p["request_id"]].results == []


def test_read_only_has_no_execution_authority():
    mcp, cs = make()
    r = mcp.read(cs.context(), "iam.inspect", {"role": "arn:role/x"})
    assert r["outcome"] == "ALLOW" and r["read_only"] and r["execution_token"] is None


def test_simulation_bound_to_action_and_structured():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": "w"})
    mcp.evaluate(cs.context(), p["request_id"])
    r = mcp.simulate(cs.context(), p["request_id"])
    assert r["outcome"] == "ALLOW"
    rec = mcp.gateway.records[p["request_id"]]
    sims = [e for e in rec.evidence if e["payload"]["kind"] == "simulation"]
    assert sims and sims[0]["payload"]["bound_to"] == rec.action_hash
    # structured, never a bare safe:true
    assert sims[0]["domain"] == "SIMULATION"


def test_changing_action_invalidates_simulation():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": "w"})
    mcp.evaluate(cs.context(), p["request_id"])
    mcp.simulate(cs.context(), p["request_id"])
    rec = mcp.gateway.records[p["request_id"]]
    # a different action would have a different hash; the bound sim would not apply
    other = copy.deepcopy(rec.envelope)
    other["arguments"] = {"workspace": "OTHER", "changes": "1"}
    assert ref_projection.action_hash(other) != rec.action_hash


def test_approval_bound_to_exact_action_and_policy():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "kubernetes.delete",
                    {"namespace": "prod", "kind": "statefulset", "name": "db"})
    mcp.evaluate(cs.context(), p["request_id"], evidence=[backup(mcp, p["action_hash"])])
    ap = mcp.create_test_approval(p["request_id"])
    assert ap["payload"]["action_hash"] == p["action_hash"]
    assert ap["payload"]["policy_hash"] == mcp.gateway.signed_policy["policy_hash"]
    r = mcp.attach_approval(cs.context(), p["request_id"], ap)
    assert r["outcome"] == "ALLOW"


def test_escalation_entry_is_complete():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "kubernetes.delete",
                    {"namespace": "prod", "kind": "statefulset", "name": "db"})
    mcp.evaluate(cs.context(), p["request_id"], evidence=[backup(mcp, p["action_hash"])])
    e = mcp.list_escalations()["escalations"][0]
    for k in ("action_hash", "action_summary", "dispositive_rules", "approval_scope",
              "consequence", "required_approver_roles", "expiry", "correlation_id"):
        assert k in e and e[k] is not None


def test_constraints_bound_into_token_not_just_returned():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "filesystem.write", {"path": "a", "content": "b"})
    mcp.evaluate(cs.context(), p["request_id"])
    r = mcp.simulate(cs.context(), p["request_id"])
    assert r["applied_constraints"]  # ALLOW_WITH_CONSTRAINTS
    rec = mcp.gateway.records[p["request_id"]]
    assert rec.token["payload"]["constraints"] == rec.decision["applied_constraints"]
    x = mcp.execute(cs.context(), p["request_id"])
    assert x["state"] == "COMPLETED"


def test_deterministic_repeated_evaluation():
    outs = []
    for _ in range(2):
        mcp, cs = make()
        p = mcp.prepare(cs.context(), "iam.grant",
                        {"role": "arn:role/x", "grantee": "agent://sre/1"})
        outs.append(mcp.evaluate(cs.context(), p["request_id"])["outcome"])
    assert outs[0] == outs[1] == "DENY"
