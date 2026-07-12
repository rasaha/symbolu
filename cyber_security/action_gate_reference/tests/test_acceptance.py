"""Acceptance scenarios A1-A14 (spec §11 acceptance list / MVP §10).

Each asserts the gate's fail-closed disposition for a specific attack or
missing-precondition scenario. Outcomes are the six frozen decisions.
"""

from __future__ import annotations

import copy

import pytest

from action_gate_ref import gate, projection, token as token_mod
from action_gate_ref.errors import NonceReplayError, StaleStateError
from tests import helpers as H

DUAL = [H.APPROVERS["security-lead"], H.APPROVERS["sre-lead"]]


def _eval(e, *, evidence=None, approvals=None, now=H.NOW, used_nonces=()):
    return gate.evaluate(e, H.signed_policy(), evidence=evidence, approvals=approvals,
                         now=now, used_nonces=used_nonces)


def test_A1_missing_attestation_requests_evidence():
    # IAM with valid dual approval but no attestation -> REQUEST_MORE_EVIDENCE.
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL)
    d = _eval(e, approvals=[ap])
    assert d["outcome"] == "REQUEST_MORE_EVIDENCE"


def test_A2_expired_approval_denied():
    e = H.with_attestation(H.env_for("IAM_GRANT_ADMIN"))
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL,
                        exp="2026-07-12T14:00:00.000Z")  # already expired at NOW
    d = _eval(e, approvals=[ap])
    assert d["outcome"] == "DENY"


def test_A3_policy_mismatch_denied():
    e = H.with_attestation(H.env_for("IAM_GRANT_ADMIN"))
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL,
                        policy_hash="stale-policy-hash")
    d = _eval(e, approvals=[ap])
    assert d["outcome"] == "DENY"


def test_A4_missing_backup_denied():
    # Irreversible destructive class: hard MUST_HAVE precondition -> DENY (finding #1).
    e = H.env_for("DB_DELETE", reversibility="REVERSIBLE_WITH_COST")
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL)
    d = _eval(e, approvals=[ap])  # no backup evidence
    assert d["outcome"] == "DENY"
    assert "R3" in d["dispositive_rules"]


def test_A5_unavailable_simulation_retries():
    e = H.env_for("DEPLOY")
    d = _eval(e, evidence=[H.ev_signed_artifact(e)])  # artifact present, simulation absent
    assert d["outcome"] == "SIMULATE_AND_RETRY"


def test_A6_stale_state_requests_evidence():
    e = H.env_for("NET_EXPOSE", args={"public": False, "target_sensitive": False})
    e["state_freshness"] = {"as_of": "2026-07-12T13:00:00.000Z", "source": "iam-live"}
    d = _eval(e)  # ~65 min old, bound 600s
    assert d["outcome"] == "REQUEST_MORE_EVIDENCE"
    assert "FRESHNESS" in d["dispositive_rules"]


def test_A7_credential_scope_expansion_denied():
    e = H.env_for("IAM_GRANT_ADMIN")
    e["delegation_chain"] = [{"from": "user://alice", "to": "agent://sre/1",
                              "grant": "iam:read", "exp": "2026-07-12T18:00:00.000Z"}]
    e["credential_scope"] = {"principal": "agent://sre/1",
                             "permissions": ["iam:AttachRolePolicy"], "ttl": "PT10M"}
    d = _eval(e)
    assert d["outcome"] == "DENY"
    assert "PRIV_MONO" in d["dispositive_rules"]


def test_A8_self_authored_ticket_denied():
    e = H.env_for("DEPLOY")
    e["linked_ticket"] = "CHG-1"
    e["arguments"] = dict(e["arguments"], ticket_author="user://alice")  # == delegator
    d = _eval(e, evidence=[H.ev_signed_artifact(e), H.ev_sim(e)])
    assert d["outcome"] == "DENY"
    assert "TICKET_SOD" in d["dispositive_rules"]


def test_A9_approval_modification_denied():
    e = H.with_attestation(H.env_for("IAM_GRANT_ADMIN"))
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL)
    ap = copy.deepcopy(ap)
    ap["payload"]["constraints"] = {"injected": "escalation"}  # tamper after signing
    d = _eval(e, approvals=[ap])
    assert d["outcome"] == "DENY"


def test_A10_action_modification_denied():
    e = H.with_attestation(H.env_for("IAM_GRANT_ADMIN"))
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL)
    e2 = copy.deepcopy(e)
    e2["arguments"] = {"grantee": "arn:aws:iam::acct:role/ESCALATED"}  # changed after approval
    d = _eval(e2, approvals=[ap])
    assert d["outcome"] == "DENY"


def test_A11_replayed_token_rejected():
    e = H.env_for("DEPLOY")
    tok = token_mod.build_token(
        action_hash=projection.action_hash(e), permitted_operation=e["operation"],
        permitted_target=e["target_resource"], credential_scope=e["credential_scope"],
        constraints={}, expiration=H.APPROVAL_EXP, nonce="tok-replay",
        policy_hash="ph", decision_record_hash="dr")
    assert token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW)
    with pytest.raises(NonceReplayError):
        token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW,
                               used_nonces={"tok-replay"})


def test_A12_toctou_state_mismatch_rejected():
    e = H.env_for("DEPLOY")
    tok = token_mod.build_token(
        action_hash=projection.action_hash(e), permitted_operation=e["operation"],
        permitted_target=e["target_resource"], credential_scope=e["credential_scope"],
        constraints={}, expiration=H.APPROVAL_EXP, nonce="tok-toctou",
        policy_hash="ph", decision_record_hash="dr")
    with pytest.raises(StaleStateError):
        token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW,
                               current_state_hash="sha256:" + "ef" * 32)


def test_A13_deterministic_repeated_evaluation():
    e, ev, aps, _ = H.happy("DB_DELETE")
    sp = H.signed_policy()
    outs = {gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)["outcome"]
            for _ in range(5)}
    assert outs == {"ALLOW"}


def test_A14_self_grant_denied():
    e = H.env_for("IAM_GRANT_ADMIN", args={"grantee": "agent://sre/1"})  # grantee == principal
    ap = H.approval_for(e, H.signed_policy(), approver_policy="dual_control", approvers=DUAL)
    d = _eval(e, approvals=[ap])
    assert d["outcome"] == "DENY"
    assert "R1" in d["dispositive_rules"]
