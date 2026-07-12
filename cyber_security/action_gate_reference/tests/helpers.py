"""Shared builders for transition/acceptance scenarios."""

from __future__ import annotations

import copy

from action_gate_ref import policy, projection
from action_gate_ref import approval as approval_mod
from action_gate_ref import evidence as evidence_mod
from action_gate_ref import token as token_mod
from action_gate_ref.conformance import ref_envelope

NOW = "2026-07-12T14:05:00.000Z"
ATTN_EXP = "2026-07-12T14:10:00.000Z"
APPROVAL_EXP = "2026-07-12T15:00:00.000Z"

_OP_DEFAULTS = {
    "IAM_GRANT_ADMIN": (["arn:aws:iam::acct:role/x"], {"grantee": "arn:aws:iam::acct:role/other"},
                        "REVERSIBLE_WITH_COST"),
    "DEPLOY": (["svc://billing"], {}, "REVERSIBLE"),
    "DB_DELETE": (["db://prod/orders"], {"last_replica": False}, "IRREVERSIBLE"),
    "NET_EXPOSE": (["net://sg-1"], {"public": True, "target_sensitive": True}, "REVERSIBLE"),
    "SECRET_READ": (["secret://prod/db"], {"export": False, "bulk": False, "sink_approved": True},
                    "IRREVERSIBLE"),
    "MONITORING_DISABLE": (["mon://prod"], {"target": "gate_audit_path"}, "REVERSIBLE"),
    "DB_MUTATION": (["db://prod/orders#t"], {"unbounded": False, "affected_count": "100"},
                    "REVERSIBLE_WITH_COST"),
    "KEY_ROTATE": (["key://prod/k1"], {"live_dependents": True, "trust_root_outside": False},
                   "REVERSIBLE_WITH_COST"),
    "CLOUD_SPEND_INCREASE": (["budget://prod"], {"self_approved": True}, "REVERSIBLE"),
    "EXTERNAL_COMMS": (["comms://customers"], {"content_type": "free_text"}, "IRREVERSIBLE"),
}


def env_for(operation, *, args=None, target=None, reversibility=None, **over):
    e = ref_envelope()
    tgt, dargs, rev = _OP_DEFAULTS[operation]
    e["operation"] = operation
    e["target_resource"] = target if target is not None else list(tgt)
    e["arguments"] = args if args is not None else dict(dargs)
    e["reversibility"] = reversibility or rev
    # broad delegation so privilege-monotonicity passes on happy paths
    e["delegation_chain"] = [{"from": "user://alice", "to": "agent://sre/1",
                              "grant": "*", "exp": "2026-07-12T18:00:00.000Z"}]
    e["credential_scope"] = {"principal": "agent://sre/1", "permissions": ["op:do"], "ttl": "PT10M"}
    for k, v in over.items():
        e[k] = v
    return e


def with_attestation(e, *, attn_type="workload-identity", exp=ATTN_EXP):
    e = copy.deepcopy(e)
    e["attestation"] = {"type": attn_type, "evidence": "deadbeef", "exp": exp}
    return e


def signed_policy():
    return policy.sign_policy(policy.build_bundle())


def approval_for(e, sp, *, approver_policy, approvers, constraints=None, exp=APPROVAL_EXP,
                 nonce="ap-1", policy_hash=None):
    ah = projection.action_hash(e)
    return approval_mod.build_approval(
        action_hash=ah, policy_hash=policy_hash or sp["policy_hash"],
        approver_policy=approver_policy, approvers=approvers,
        approval_scope={"operation": e["operation"], "target": e["target_resource"]},
        constraints=constraints or {}, issued_at="2026-07-12T13:00:00.000Z",
        expiration=exp, nonce=nonce)


def ev_backup(e):
    return evidence_mod.build_evidence(
        bound_to=projection.action_hash(e), producer="restore-checker",
        generated_at=NOW, valid_until="2026-07-12T14:15:00.000Z", evidence_version="1",
        kind="verified_restorable_backup", fidelity_or_confidence="HIGH",
        content={"backup_id": "b1", "restore_tested": True})


def ev_signed_artifact(e):
    return evidence_mod.build_evidence(
        bound_to=projection.action_hash(e), producer="registry", generated_at=NOW,
        valid_until="2026-07-12T14:15:00.000Z", evidence_version="1", kind="signed_artifact",
        fidelity_or_confidence="HIGH", content={"artifact": "sha256:abc", "signed": "yes"})


def ev_sim(e, *, fidelity="HIGH"):
    return evidence_mod.build_evidence(
        bound_to=projection.action_hash(e), producer="terraform-plan", generated_at=NOW,
        valid_until="2026-07-12T14:15:00.000Z", evidence_version="1", kind="simulation",
        fidelity_or_confidence=fidelity, is_simulation=True,
        content={"coverage": "0.9", "predicted_changes": [], "affected_resources": []})


APPROVERS = {
    "security-lead": {"id": "security-lead", "key_id": "approver:security-lead"},
    "sre-lead": {"id": "sre-lead", "key_id": "approver:sre-lead"},
    "budget-owner": {"id": "budget-owner", "key_id": "approver:budget-owner"},
    "comms-owner": {"id": "comms-owner", "key_id": "approver:comms-owner"},
}

_DUAL = [APPROVERS["security-lead"], APPROVERS["sre-lead"]]

# Fully-satisfied "happy path" per operation: (envelope-overrides, evidence-kinds,
# approver_policy, approvers, attestation?, expected-outcome). Drives both the
# transition tests and fixtures/transitions.json.
_HAPPY = {
    "IAM_GRANT_ADMIN": (dict(), [], "dual_control", _DUAL, True, "ALLOW"),
    "DEPLOY": (dict(), ["signed_artifact", "sim_high"], None, [], False, "ALLOW"),
    "DB_DELETE": (dict(reversibility="REVERSIBLE_WITH_COST"), ["backup"],
                  "dual_control", _DUAL, False, "ALLOW"),
    "NET_EXPOSE": (dict(args={"public": False, "target_sensitive": False}), [],
                   None, [], False, "ALLOW"),
    "SECRET_READ": (dict(), [], "single", [APPROVERS["security-lead"]], False,
                    "ALLOW_WITH_CONSTRAINTS"),
    "MONITORING_DISABLE": (dict(args={"target": "mon://prod/app"}), [],
                           "dual_control", _DUAL, False, "ALLOW_WITH_CONSTRAINTS"),
    "DB_MUTATION": (dict(), ["sim_medium"], None, [], False, "ALLOW_WITH_CONSTRAINTS"),
    "KEY_ROTATE": (dict(args={"live_dependents": False, "trust_root_outside": False}),
                   [], None, [], False, "ALLOW"),
    "CLOUD_SPEND_INCREASE": (dict(args={"self_approved": False}), [], None, [], False,
                             "ALLOW"),
    "EXTERNAL_COMMS": (dict(args={"content_type": "template"}),
                       [], "comms_owner", [APPROVERS["comms-owner"]], False,
                       "ALLOW_WITH_CONSTRAINTS"),
}


def happy(operation):
    """Return (envelope, evidence, approvals, expected_outcome) for a satisfied path."""
    overrides, ev_kinds, approver_policy, approvers, need_attn, expected = _HAPPY[operation]
    e = env_for(operation, **overrides)
    if need_attn:
        e = with_attestation(e)
    ev = []
    for k in ev_kinds:
        if k == "signed_artifact":
            ev.append(ev_signed_artifact(e))
        elif k == "backup":
            ev.append(ev_backup(e))
        elif k == "sim_high":
            ev.append(ev_sim(e, fidelity="HIGH"))
        elif k == "sim_medium":
            ev.append(ev_sim(e, fidelity="MEDIUM"))
    sp = signed_policy()
    approvals = []
    if approvers:
        approvals.append(approval_for(e, sp, approver_policy=approver_policy,
                                      approvers=approvers))
    return e, ev, approvals, expected
