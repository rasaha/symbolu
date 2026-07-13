"""Tier 2 — naturalistic fixtures.

Authored to read like real tickets/policies/action requests, with phrasing the
narrow reference extractor is designed to recognize (so realistic ~ oracle here).

PROVENANCE NOTE: these are AUTHORED, not harvested from production logs. Genuine
NATURALISTIC_REPO provenance (real, licensed action contexts) is not available in
this environment, so origin is SYNTHETIC and the run verdict stays locked. This is
deliberate and documented — the pipeline is exercised on naturalistic *shape*
without claiming real-data provenance.
"""

from __future__ import annotations

from ..origin import SYNTHETIC
from ..units import Context, SemanticUnit as U


def deploy_ticket() -> Context:
    return Context(
        id="t2_deploy_ticket", data_origin=SYNTHETIC,
        description="A realistic deploy ticket; sim + artifact are decisive.",
        base={"tool": "terraform", "verb": "apply", "target": ["svc://billing"], "args": {}},
        units=(
            U(id="hdr", source_type="chat_turn",
              text="Ticket OPS-3391: apply the billing Terraform change for Q3 pricing."),
            U(id="artifact", source_type="evidence_record",
              text="CI attached a signed artifact for commit 9f2a1c."),
            U(id="sim", source_type="evidence_record",
              text="A high fidelity simulation of the plan completed with no drift.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]}),
            U(id="ctx1", source_type="sentence",
              text="This change adjusts three pricing tiers in the billing module."),
            U(id="art2", source_type="evidence_record",
              text="The signed artifact was verified against the registry.",
              contrib={"evidence": [{"kind": "signed_artifact"}]}),
        ))


def secret_export() -> Context:
    return Context(
        id="t2_secret_export", data_origin=SYNTHETIC,
        description="Secret read with export to an approved sink; approver required.",
        base={"tool": "filesystem", "verb": "read", "target": ["file://secrets/api"],
              "args": {"export": True}},
        units=(
            U(id="why", source_type="sentence",
              text="The audit team needs the API credentials exported for the quarterly review."),
            U(id="sink", source_type="policy_rule",
              text="The destination bucket is on the approved sink allowlist (sink approved).",
              contrib={"args": {"sink_approved": True}}),
            U(id="appr", source_type="approval_record",
              text="Approved by the security lead (single approver).",
              contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]}),
            U(id="note", source_type="sentence",
              text="Credentials will be rotated after the read completes."),
        ))


def db_delete_change() -> Context:
    return Context(
        id="t2_db_delete", data_origin=SYNTHETIC,
        description="Replica delete with verified backup and dual-control approval.",
        base={"tool": "kubernetes", "verb": "delete", "target": ["db://replica/3"],
              "args": {}, "reversibility": "REVERSIBLE_WITH_COST"},
        units=(
            U(id="scope", source_type="sentence",
              text="Decommission the third read replica after the migration."),
            U(id="backup", source_type="evidence_record",
              text="A verified backup exists and a restore was tested last night.",
              contrib={"evidence": [{"kind": "verified_restorable_backup"}]}),
            U(id="appr", source_type="approval_record",
              text="Dual control approval recorded from security and SRE leads.",
              contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]}),
            U(id="drain", source_type="log_event",
              text="Replica drained of live traffic at 01:12 UTC."),
        ),
        linked_pairs=(("backup", "appr", "backup_and_approval"),))


def mutation_scope() -> Context:
    return Context(
        id="t2_mutation_scope", data_origin=SYNTHETIC,
        description="Bounded DB mutation; the row count is an envelope field.",
        base={"tool": "filesystem", "verb": "write", "target": ["db://accounts"], "args": {}},
        units=(
            U(id="desc", source_type="sentence",
              text="Backfill the new status column across the accounts table."),
            U(id="sim", source_type="evidence_record",
              text="A medium fidelity simulation estimated the change.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "MEDIUM"}]}),
            U(id="count", source_type="table_row",
              text="| affected | 8000 records |",
              contrib={"args": {"affected_count": "8000"}}),
        ))


ALL_FIXTURES = [deploy_ticket, secret_export, db_delete_change, mutation_scope]


def load() -> list:
    return [f() for f in ALL_FIXTURES]
