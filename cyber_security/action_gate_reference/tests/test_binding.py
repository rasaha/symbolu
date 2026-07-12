"""Binding & replay protections: approval, token, audit chain (spec §11/§14/§15)."""

from __future__ import annotations

import copy

import pytest

from action_gate_ref import audit as audit_mod
from action_gate_ref import approval as approval_mod
from action_gate_ref import projection, token as token_mod
from action_gate_ref.errors import (
    ActionHashMismatchError, ConstraintsChangedError, ExpiredError,
    NonceReplayError, PolicyMismatchError, ScopeViolationError,
    StaleStateError, TargetMismatchError,
)
from tests import helpers as H


# ---------------- approval binding (spec §11) ----------------

def _approval(e, sp, **over):
    kw = dict(approver_policy="dual_control",
              approvers=[H.APPROVERS["security-lead"], H.APPROVERS["sre-lead"]])
    kw.update(over)
    return H.approval_for(e, sp, **kw)


def test_approval_valid():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp)
    assert approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW)


def test_approval_action_modification_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp)
    e2 = copy.deepcopy(e)
    e2["arguments"] = {"grantee": "arn:aws:iam::acct:role/TAMPERED"}
    with pytest.raises(ActionHashMismatchError):
        approval_mod.verify_approval(ap, e2, active_policy_hash=sp["policy_hash"], now=H.NOW)


def test_approval_policy_mismatch_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp)
    with pytest.raises(PolicyMismatchError):
        approval_mod.verify_approval(ap, e, active_policy_hash="different", now=H.NOW)


def test_approval_expiry_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp)
    with pytest.raises(ExpiredError):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"],
                                     now="2026-07-12T16:00:00.000Z")


def test_approval_nonce_replay_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp, nonce="ap-x")
    with pytest.raises(NonceReplayError):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW,
                                     used_nonces={"ap-x"})


def test_approval_changed_constraints_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp, constraints={"a": "1"})
    with pytest.raises(ConstraintsChangedError):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW,
                                     expected_constraints={"a": "2"})


def test_approval_scope_not_subsumed_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    # approval scoped to a different target than the action
    ah = projection.action_hash(e)
    ap = approval_mod.build_approval(
        action_hash=ah, policy_hash=sp["policy_hash"], approver_policy="dual_control",
        approvers=[H.APPROVERS["security-lead"], H.APPROVERS["sre-lead"]],
        approval_scope={"operation": "IAM_GRANT_ADMIN", "target": ["arn:aws:iam::acct:role/OTHER"]},
        constraints={}, issued_at="2026-07-12T13:00:00.000Z",
        expiration=H.APPROVAL_EXP, nonce="ap-scope")
    with pytest.raises(ScopeViolationError):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW)


def test_approval_sod_self_approval_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    # approver id == agent principal (agent://sre/1) violates SoD
    ah = projection.action_hash(e)
    ap = approval_mod.build_approval(
        action_hash=ah, policy_hash=sp["policy_hash"], approver_policy="dual_control",
        approvers=[{"id": "agent://sre/1", "key_id": "approver:security-lead"},
                   H.APPROVERS["sre-lead"]],
        approval_scope={"operation": e["operation"], "target": e["target_resource"]},
        constraints={}, issued_at="2026-07-12T13:00:00.000Z",
        expiration=H.APPROVAL_EXP, nonce="ap-sod")
    with pytest.raises(ScopeViolationError):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW)


def test_approval_insufficient_quorum_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp, approvers=[H.APPROVERS["security-lead"]])  # only 1 for dual_control
    with pytest.raises(ScopeViolationError):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW)


def test_approval_tampered_signature_rejected():
    sp = H.signed_policy()
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = _approval(e, sp)
    ap = copy.deepcopy(ap)
    ap["signatures"][0]["sig"] = "00" * 32
    with pytest.raises(Exception):
        approval_mod.verify_approval(ap, e, active_policy_hash=sp["policy_hash"], now=H.NOW)


# ---------------- execution token (spec §15) ----------------

def _token(e, **over):
    kw = dict(action_hash=projection.action_hash(e), permitted_operation=e["operation"],
              permitted_target=e["target_resource"], credential_scope=e["credential_scope"],
              constraints={}, expiration=H.APPROVAL_EXP, nonce="tok-1",
              policy_hash="ph", decision_record_hash="dr")
    kw.update(over)
    return token_mod.build_token(**kw)


def test_token_valid():
    e = H.env_for("DEPLOY")
    tok = _token(e)
    assert token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW)


def test_token_expired_rejected():
    e = H.env_for("DEPLOY")
    tok = _token(e, expiration="2026-07-12T14:00:00.000Z")
    with pytest.raises(ExpiredError):
        token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW)


def test_token_replay_rejected():
    e = H.env_for("DEPLOY")
    tok = _token(e, nonce="tok-r")
    with pytest.raises(NonceReplayError):
        token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW,
                               used_nonces={"tok-r"})


def test_token_action_modification_rejected():
    e = H.env_for("DEPLOY")
    tok = _token(e)
    e2 = copy.deepcopy(e)
    e2["arguments"] = {"changed": "yes"}
    with pytest.raises(ActionHashMismatchError):
        token_mod.verify_token(tok, e2, active_policy_hash="ph", now=H.NOW)


def test_token_retarget_rejected():
    e = H.env_for("DEPLOY")
    tok = _token(e, permitted_target=["svc://only-this"])
    with pytest.raises((TargetMismatchError, ActionHashMismatchError)):
        token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW)


def test_token_toctou_state_mismatch_rejected():
    e = H.env_for("DEPLOY")
    tok = _token(e)
    with pytest.raises(StaleStateError):
        token_mod.verify_token(tok, e, active_policy_hash="ph", now=H.NOW,
                               current_state_hash="sha256:" + "cd" * 32)


def test_token_policy_reeval_rejected():
    e = H.env_for("DEPLOY")
    tok = _token(e, policy_hash="old-policy")
    with pytest.raises(PolicyMismatchError):
        token_mod.verify_token(tok, e, active_policy_hash="new-policy", now=H.NOW,
                               require_reeval=True)


# ---------------- audit chain (spec §14) ----------------

def _record(i):
    return audit_mod.build_audit_record(
        action_hash=f"a{i}", decision="ALLOW", dispositive_rules=["R2"],
        policy_hash="ph", evidence_hashes=[], approval_hashes=[],
        applied_constraints=None, timestamps={"decided": H.NOW})


def test_audit_chain_verifies_intact():
    ch = audit_mod.AuditChain("c1")
    for i in range(5):
        ch.append(_record(i))
    assert ch.verify()
    assert ch.locate_tamper() is None


def test_audit_chain_detects_payload_tamper():
    ch = audit_mod.AuditChain("c1")
    for i in range(5):
        ch.append(_record(i))
    ch.records[2]["payload"]["decision"] = "DENY"
    assert not ch.verify()
    assert ch.locate_tamper() == 2


def test_audit_chain_detects_reorder():
    ch = audit_mod.AuditChain("c1")
    for i in range(4):
        ch.append(_record(i))
    ch.records[1], ch.records[2] = ch.records[2], ch.records[1]
    assert not ch.verify()


def test_audit_record_self_verifies():
    rec = _record(0)
    assert audit_mod.verify_record(rec)
    rec["payload"]["decision"] = "DENY"
    assert not audit_mod.verify_record(rec)
