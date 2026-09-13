"""Shared builders for the suite. Every instant-free, every value synthetic."""

from __future__ import annotations

from ugence_workflow_drafts import WorkflowDraft, build_draft

TENANT = "tenant-1"
OTHER = "tenant-2"
RECORDED_BY = "governance-studio-private-hosted/0.13.0"
VALIDATED_BY = "ugence-agent-workforce-composer/0.2.1"


def document(**over) -> dict:
    base = {
        "ir_version": "workflow_ir.v2",
        "workflow_id": "wf_synthetic",
        "nodes": [{"node_id": "n1", "kind": "DECISION_RULE"}, {"node_id": "n2", "kind": "TERMINAL_OUTCOME"}],
        "edges": [{"edge_id": "e1", "source_id": "n1", "target_id": "n2"}],
    }
    base.update(over)
    return base


def draft(**over) -> WorkflowDraft:
    kwargs = dict(tenant_id=TENANT, title="Procurement intake", contract_version="workflow_ir.v2",
                  workflow=document(), claimed_owner_ref="directory://people/owner-1",
                  recorded_by=RECORDED_BY, validated_by=VALIDATED_BY)
    kwargs.update(over)
    return build_draft(**kwargs)
