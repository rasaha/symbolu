# Persistence Records

> Every durable record is an **immutable, content-addressed envelope** around a
> canonical payload. Externally-owned authoritative records are stored **only as
> audit projections** — reference + content hash + minimal linkage — never as
> newly issued authority.

Machine-readable companion: `docs/record_types.json`.

## Record envelope

```
RecordEnvelope(
  record_id, record_type, schema_version, tenant_id, workflow_id,
  workflow_revision_id, created_at, canonical_payload,
  payload_fingerprint, previous_record_fingerprint, envelope_fingerprint)
```

`canonical_payload` is produced by the data-minimizing serializer
(`DATA_MINIMIZATION.md`). `payload_fingerprint` and `envelope_fingerprint` are
recomputed on every verify, reconstruction, and bundle check.

## Record types

Product-owned records:

- `GOVERNED_CHANGE_IDENTITY`, `EVIDENCE_RECORD`, `CLAIM_MANIFEST`,
  `CLAIM_EVALUATION`, `GOVERNANCE_RECOMMENDATION`, `PREPARED_MERGE_ACTION`,
  `OPERATIONAL_SNAPSHOT`, `TRUSTED_SIGNAL_PROJECTION`,
  `ACTION_CLEARANCE_EVALUATION`, `HUMAN_INTERVENTION_ASSESSMENT`,
  `WORKFLOW_REVISION`, `GOVERNANCE_CHAIN`.

External **audit projections** (of records owned by other capabilities):

- `TAP_RESULT_PROJECTION`, `DECISION_RECORD_PROJECTION`,
  `CONTEXT_ENVELOPE_PROJECTION` (CER), `ACTIONGATE_RESULT_PROJECTION`,
  `CLEARANCE_REQUEST_PROJECTION`.

A projection stores the upstream record's **identity + content hash** and the
minimal linkage the chain needs. It is audit evidence of an authoritative record,
never a substitute for it, and the durable store never mints one.

## Deterministic record ids

Record ids are content/reference-derived so re-runs are idempotent and
reconstruction can resolve links without a side table:

| Record | id derivation |
|---|---|
| change identity | `gci:<change_fingerprint>` |
| evidence | `<evidence_id>` |
| claim manifest | `<manifest_id>` |
| decision projection | `decproj:<decision_id>` |
| CER projection | `cerproj:<cer_id>` |
| prepared action | `pma:<action_fingerprint>` |
| ActionGate projection | `agproj:<result_fingerprint>` |
| TAP projection | `tapproj:<manifest_fingerprint>` |
| clearance request | `clreq:<request_fingerprint>` |
| clearance evaluation | `<evaluation_record_id>` |
| intervention | `<assessment_id>` |
| workflow revision | `rev:<revision_id>` |
| governance chain | `<chain_id>` |

## The `GOVERNANCE_CHAIN` payload

The finalized chain payload is a minimal, data-minimized **reference/linkage
projection**: identifiers, content hashes, the clearance/intervention summary, and
the mandatory `execution_status: "DISABLED"` marker. Its keys are the shared
contract between the finalizer, durable reconstruction, and the audit bundle. It
is never an authority record and never carries a diff, token, or secret.
