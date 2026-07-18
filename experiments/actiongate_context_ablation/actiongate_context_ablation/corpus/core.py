"""Scenario cores: per-action-type critical spans + base, parameterized by phrasing.

Each core returns (base, critical_units, linked_pairs). The item builder appends
realistic filler. Phrasing has two modes:
  * recognized  (DEV / VALIDATION): text contains keywords the realistic extractor
    knows -> low extractor instability.
  * paraphrased (HELDOUT): the same facts in wording the extractor does not know
    -> measures held-out extractor instability.
The ORACLE contrib is identical in both modes (ground truth), so held-out true
criticality is unchanged; only the realistic extractor diverges.

Attestation exp / timestamps are future-dated relative to the fixed EVAL_NOW.
"""

from __future__ import annotations

from .builders import (
    ASSURANCE_CRITICAL, DECISION_CRITICAL, ENVELOPE_CRITICAL, REDUNDANT,
    STRUCTURE_CRITICAL, span,
)

_ATTN = {"type": "workload-identity", "evidence": "deadbeef", "exp": "2026-07-12T15:00:00.000Z"}


def _txt(recognized, paraphrased, para):
    return paraphrased if para else recognized


def deploy(target, para=False):
    base = {"tool": "terraform", "verb": "apply", "target": list(target), "args": {}}
    crit = [
        span("art", "evidence_record",
             _txt("A signed build artifact from CI is attached.",
                  "CI produced a provenance-stamped image for this rollout.", para),
             contrib={"evidence": [{"kind": "signed_artifact"}]}, expected=DECISION_CRITICAL),
        span("sim", "evidence_record",
             _txt("A high-fidelity deployment simulation passed with no drift.",
                  "We ran a full dress rehearsal of the rollout and saw nothing unexpected.", para),
             contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]},
             expected=DECISION_CRITICAL),
    ]
    return base, crit, ()


def k8s_apply(target, para=False):
    base, crit, lp = deploy(target, para)
    base["tool"], base["verb"] = "kubernetes", "apply"
    return base, crit, lp


def delete(target, para=False):
    base = {"tool": "kubernetes", "verb": "delete", "target": list(target), "args": {}}
    crit = [
        span("backup", "evidence_record",
             _txt("A verified restorable backup exists and a restore was tested last night.",
                  "We hold a point-in-time copy that we successfully brought back last night.", para),
             contrib={"evidence": [{"kind": "verified_restorable_backup"}]},
             expected=DECISION_CRITICAL),
        span("appr", "approval_record",
             _txt("Dual control approval recorded from the security and SRE leads.",
                  "Two leads put their names on the change in the review channel.", para),
             contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]},
             expected=DECISION_CRITICAL),
        span("rollback", "clause",
             _txt("Rollback plan: restore from the verified backup (reversible with cost).",
                  "If needed we can walk it back by restoring the copy, at some cost.", para),
             contrib={"reversibility": "REVERSIBLE_WITH_COST"}, expected=ASSURANCE_CRITICAL),
    ]
    return base, crit, (("backup", "appr", "backup_and_approval"),)


def iam_grant(target, para=False):
    base = {"tool": "iam", "verb": "grant", "target": list(target), "args": {}}
    crit = [
        span("appr", "approval_record",
             _txt("Dual control approval from security and SRE leads.",
                  "Two named leads signed off in the change record.", para),
             contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]},
             expected=DECISION_CRITICAL),
        span("attest", "evidence_record",
             _txt("Workload-identity attestation is attached for the grantee.",
                  "The grantee's runtime presented a verified machine credential.", para),
             contrib={"attestation": _ATTN}, expected=ASSURANCE_CRITICAL),
    ]
    return base, crit, ()


def secret_export(target, para=False):
    base = {"tool": "filesystem", "verb": "read", "target": list(target),
            "args": {"export": True}}
    crit = [
        span("sink", "policy_rule",
             _txt("The export destination is on the approved sink allowlist.",
                  "The destination was cleared by infosec ahead of time.", para),
             contrib={"args": {"sink_approved": True}}, expected=DECISION_CRITICAL),
        span("appr", "approval_record",
             _txt("Approved by the security lead (single approver).",
                  "A manager gave the go-ahead for this pull.", para),
             contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]},
             expected=DECISION_CRITICAL),
    ]
    return base, crit, ()


def netpol(target, para=False):
    base = {"tool": "http", "verb": "request", "target": list(target),
            "args": {"widening": True}}
    crit = [
        span("appr", "approval_record",
             _txt("The widening was approved by the security lead (single approver).",
                  "Security gave a thumbs up to broadening the ingress.", para),
             contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]},
             expected=DECISION_CRITICAL),
    ]
    return base, crit, ()


def db_migration(target, para=False):
    base = {"tool": "filesystem", "verb": "write", "target": list(target), "args": {}}
    crit = [
        span("sim", "evidence_record",
             _txt("A medium-fidelity simulation estimated the migration impact.",
                  "A partial trial run gave us an estimate of the change.", para),
             contrib={"evidence": [{"kind": "simulation", "fidelity": "MEDIUM"}]},
             expected=DECISION_CRITICAL),
        span("count", "table_row",
             "| affected | 8000 records |",
             contrib={"args": {"affected_count": "8000"}}, expected=ENVELOPE_CRITICAL),
    ]
    return base, crit, ()


def monitoring_disable(target, para=False):
    base = {"tool": "monitoring", "verb": "disable", "target": list(target), "args": {}}
    crit = [
        span("appr", "approval_record",
             _txt("Dual control approval to disable monitoring during the maintenance window.",
                  "Two leads agreed in the channel to silence alerts for the window.", para),
             contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]},
             expected=DECISION_CRITICAL),
    ]
    return base, crit, ()


def refund(target, para=False):
    # payment/refund modeled as a bounded DB mutation; the amount is envelope-critical
    base = {"tool": "filesystem", "verb": "write", "target": list(target), "args": {},
            "evidence": [{"kind": "simulation", "fidelity": "MEDIUM"}]}
    crit = [
        span("amount", "json_field",
             '{"refund_amount": "4200", "currency": "USD", "affected_count": "1"}',
             contrib={"args": {"affected_count": "1", "projected_cost": "4200"}},
             expected=ENVELOPE_CRITICAL),
        span("cur", "sentence",
             "The refund is denominated in USD (see amount above).",
             references=("amount",), dependency_links=("amount",), expected=STRUCTURE_CRITICAL),
    ]
    return base, crit, (("amount", "cur", "amount_and_currency"),)


def cred_scope(target, para=False):
    base = {"tool": "filesystem", "verb": "read", "target": list(target),
            "args": {"export": True, "sink_approved": True},
            "approvals": [{"approver_policy": "single", "approvers": "single"}]}
    crit = [
        span("perm", "json_field",
             '{"extra_permissions": ["audit:tag"]}',
             contrib={"permissions_add": ["audit:tag"]}, expected=ASSURANCE_CRITICAL),
    ]
    return base, crit, ()


def storage_delete(target, para=False):
    base = {"tool": "filesystem", "verb": "delete", "target": list(target), "args": {},
            "reversibility": "REVERSIBLE_WITH_COST"}
    crit = [
        span("backup", "evidence_record",
             _txt("A verified restorable backup of the bucket exists.",
                  "There is a recent copy of the bucket we restored during a drill.", para),
             contrib={"evidence": [{"kind": "verified_restorable_backup"}]},
             expected=DECISION_CRITICAL),
        span("appr", "approval_record",
             _txt("Dual control approval for the bucket deletion.",
                  "Two leads okayed removing the bucket.", para),
             contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]},
             expected=DECISION_CRITICAL),
    ]
    return base, crit, (("backup", "appr", "backup_and_approval"),)


# action_type -> core builder
CORES = {
    "kubernetes_deploy": k8s_apply,
    "terraform_apply": deploy,
    "release_promotion": deploy,
    "service_rollback": deploy,
    "kubernetes_delete": delete,
    "iam_grant": iam_grant,
    "credential_scope_change": cred_scope,
    "secret_export": secret_export,
    "customer_data_export": secret_export,
    "network_policy": netpol,
    "database_migration": db_migration,
    "monitoring_disable": monitoring_disable,
    "incident_mitigation": monitoring_disable,
    "payment_refund": refund,
    "cloud_storage_delete": storage_delete,
    "branch_protection": db_migration,
}
