# Audit Bundle

> A governance audit bundle is **canonical JSON** that can be verified **entirely
> offline** — no store connection, no network. It is **unsigned** and makes **no
> legal non-repudiation claim**; it is tamper-*evident* through recomputable
> fingerprints, not tamper-*proof*.

Machine-readable companion: `docs/audit_bundle_manifest_schema.json`.

## Export

`export_governance_audit_bundle(store, tenant_id, workflow_id, revision_id)`
(exposed as `CodeGovernanceService.export_governance_audit_bundle`) produces:

```
{
  "manifest": { bundle_version, store_schema_version, tenant_id, workflow_id,
                workflow_revision_id, record_count, event_count,
                record_inventory, execution_status },
  "records":  [ <record envelope dicts, sorted by record_id> ],
  "events":   [ <workflow event dicts, in journal order> ],
  "chain_summary": { chain_id, clearance_status, action_clearance_status,
                     human_intervention_required, execution_status },
  "reconstruction": { state, issues },
  "execution_status": "DISABLED",
  "bundle_fingerprint": "<domain-separated SHA-256 over the body>"
}
```

## Offline verification

`verify_governance_audit_bundle(bundle)` (a `staticmethod` on the service)
requires no repository connection. It:

1. checks the `bundle_version`,
2. recomputes each record's payload and envelope fingerprint,
3. recomputes and links the event chain from `GENESIS`,
4. checks the record inventory, duplicates, and tenant/revision binding,
5. requires the governance-chain `execution_status == "DISABLED"` marker,
6. recomputes the `bundle_fingerprint` over the body.

Any mismatch is reported in `BundleVerification.issues`; `ok` is `True` only when
the list is empty.

## Determinism caveat

Exporting the **same persisted content** twice yields an identical
`bundle_fingerprint`. However, the fingerprint of a bundle produced by two
independent **full pipeline runs** is *not* guaranteed to match, because the
upstream Decision-Authority-minted CER carries a wall-clock `issued_at` /
`content_hash` (the documented MVP 1B provenance caveat) that flows into the
persisted chain. Content-addressed determinism over *fixed inputs* is proven
directly at the record/envelope/bundle level in
`tests/test_durable_persistence.py`.

## Boundary

The bundle is an audit artifact. It authorizes nothing, and its
`execution_status` is always `DISABLED`. It is not a signed attestation, not a
merge receipt, and not an execution record.
