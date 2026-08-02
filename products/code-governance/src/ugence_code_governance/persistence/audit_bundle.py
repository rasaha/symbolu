"""Deterministic, read-only governance audit bundle export + offline verification.

The bundle is canonical JSON. It is not signed and makes no legal non-repudiation
claim. Verification requires no repository connection — it recomputes all
fingerprints, verifies the event-chain linkage, the record inventory, tenant/
workflow/revision consistency, governance-chain references, and the bundle
fingerprint from the bundle alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Tuple

from . import integrity
from .durable_reconstruction import reconstruct_from_store
from .envelope import RecordEnvelope, WorkflowEventRecord
from .schema import GENESIS, RecordType, STORE_SCHEMA_VERSION
from .serialization import serialize
from .sqlite import DurableShadowStore

BUNDLE_VERSION = "code_governance.audit_bundle.v1"


def _env_dict(env: RecordEnvelope) -> Dict[str, Any]:
    return {
        "record_id": env.record_id, "record_type": env.record_type,
        "schema_version": env.schema_version, "tenant_id": env.tenant_id,
        "workflow_id": env.workflow_id, "workflow_revision_id": env.workflow_revision_id,
        "created_at": env.created_at, "canonical_payload": env.canonical_payload,
        "payload_fingerprint": env.payload_fingerprint,
        "previous_record_fingerprint": env.previous_record_fingerprint,
        "envelope_fingerprint": env.envelope_fingerprint,
    }


def _event_dict(ev: WorkflowEventRecord) -> Dict[str, Any]:
    return {
        "event_id": ev.event_id, "tenant_id": ev.tenant_id, "workflow_id": ev.workflow_id,
        "workflow_revision_id": ev.workflow_revision_id,
        "previous_event_fingerprint": ev.previous_event_fingerprint,
        "from_state": ev.from_state, "to_state": ev.to_state, "event_type": ev.event_type,
        "referenced_record_ids": list(ev.referenced_record_ids), "occurred_at": ev.occurred_at,
        "event_fingerprint": ev.event_fingerprint,
    }


def export_governance_audit_bundle(
    store: DurableShadowStore, tenant_id: str, workflow_id: str, workflow_revision_id: str,
) -> Dict[str, Any]:
    """Export a deterministic, read-only audit bundle for one workflow revision."""
    records = [e for e in store.list_for_revision(tenant_id, workflow_revision_id)]
    events = [e for e in store.events_for_workflow(tenant_id, workflow_id)
              if e.workflow_revision_id == workflow_revision_id]
    recon = reconstruct_from_store(store, tenant_id, workflow_revision_id)
    chain = next((e.canonical_payload for e in records
                  if e.record_type == RecordType.GOVERNANCE_CHAIN.value), {})
    record_dicts = [_env_dict(e) for e in sorted(records, key=lambda r: r.record_id)]
    event_dicts = [_event_dict(e) for e in events]
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "store_schema_version": STORE_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "workflow_revision_id": workflow_revision_id,
        "record_count": len(record_dicts),
        "event_count": len(event_dicts),
        "record_inventory": sorted((r["record_id"], r["record_type"]) for r in record_dicts),
        "execution_status": "DISABLED",
    }
    body = {"manifest": manifest, "records": record_dicts, "events": event_dicts,
            "chain_summary": {
                "chain_id": chain.get("chain_id", ""),
                "clearance_status": chain.get("clearance_status", ""),
                "action_clearance_status": chain.get("action_clearance_status", ""),
                "human_intervention_required": chain.get("human_intervention_required", False),
                "execution_status": chain.get("execution_status", "DISABLED"),
            },
            "reconstruction": {"state": recon.state.value, "issues": list(recon.issues)},
            "execution_status": "DISABLED"}
    body["bundle_fingerprint"] = integrity.bundle_fingerprint(serialize(body))
    return body


@dataclass(frozen=True)
class BundleVerification:
    ok: bool
    issues: Tuple[str, ...] = ()
    record_count: int = 0
    event_count: int = 0


def verify_governance_audit_bundle(bundle: Mapping[str, Any]) -> BundleVerification:
    """Verify an exported bundle entirely offline (no repository connection)."""
    issues: List[str] = []
    if bundle.get("manifest", {}).get("bundle_version") != BUNDLE_VERSION:
        return BundleVerification(False, ("unsupported bundle version",))

    manifest = bundle["manifest"]
    tenant_id = manifest["tenant_id"]
    workflow_id = manifest["workflow_id"]
    revision_id = manifest["workflow_revision_id"]
    records = bundle.get("records", [])
    events = bundle.get("events", [])

    # Bundle fingerprint (recompute over the body minus the fingerprint field).
    body = {k: v for k, v in bundle.items() if k != "bundle_fingerprint"}
    if integrity.bundle_fingerprint(serialize(body)) != bundle.get("bundle_fingerprint"):
        issues.append("bundle fingerprint mismatch")

    # Record inventory + duplicates + per-record fingerprints + tenant binding.
    seen = set()
    for r in records:
        rid = r["record_id"]
        if rid in seen:
            issues.append(f"duplicate record {rid}")
        seen.add(rid)
        if r["tenant_id"] != tenant_id:
            issues.append(f"record {rid} tenant mismatch")
        if r["workflow_revision_id"] != revision_id:
            issues.append(f"record {rid} revision mismatch")
        pfp = integrity.payload_fingerprint(r["canonical_payload"])
        if pfp != r["payload_fingerprint"]:
            issues.append(f"record {rid} payload fingerprint mismatch")
        efp = integrity.envelope_fingerprint(
            record_id=rid, record_type=r["record_type"], schema_version=r["schema_version"],
            tenant_id=r["tenant_id"], workflow_id=r["workflow_id"],
            workflow_revision_id=r["workflow_revision_id"], created_at=r["created_at"],
            payload_fp=pfp, previous_record_fingerprint=r.get("previous_record_fingerprint"))
        if efp != r["envelope_fingerprint"]:
            issues.append(f"record {rid} envelope fingerprint mismatch")
    inventory = sorted((r["record_id"], r["record_type"]) for r in records)
    if [list(x) for x in inventory] != [list(x) for x in manifest.get("record_inventory", [])] \
            and inventory != [tuple(x) for x in manifest.get("record_inventory", [])]:
        issues.append("record inventory mismatch")

    # Event-chain linkage (recompute fingerprints; verify previous linkage).
    prev = GENESIS
    for ev in events:
        if ev["tenant_id"] != tenant_id or ev["workflow_id"] != workflow_id:
            issues.append(f"event {ev['event_id']} tenant/workflow mismatch")
        if ev["previous_event_fingerprint"] != prev:
            issues.append(f"event {ev['event_id']} broken previous linkage")
        efp = integrity.event_fingerprint(
            event_id=ev["event_id"], tenant_id=ev["tenant_id"], workflow_id=ev["workflow_id"],
            workflow_revision_id=ev["workflow_revision_id"],
            previous_event_fingerprint=ev["previous_event_fingerprint"],
            from_state=ev["from_state"], to_state=ev["to_state"], event_type=ev["event_type"],
            referenced_record_ids=ev["referenced_record_ids"], occurred_at=ev["occurred_at"])
        if efp != ev["event_fingerprint"]:
            issues.append(f"event {ev['event_id']} fingerprint mismatch")
        prev = ev["event_fingerprint"]

    # Governance-chain references must be present among the records.
    chain = next((r["canonical_payload"] for r in records
                  if r["record_type"] == RecordType.GOVERNANCE_CHAIN.value), None)
    if chain is None:
        issues.append("governance chain record missing")
    else:
        if chain.get("execution_status") != "DISABLED":
            issues.append("execution-disabled marker missing/altered")

    return BundleVerification(ok=not issues, issues=tuple(issues),
                              record_count=len(records), event_count=len(events))


__all__ = [
    "BUNDLE_VERSION", "export_governance_audit_bundle",
    "verify_governance_audit_bundle", "BundleVerification",
]
