# Restart-Safe Recovery

> Recovery is **advisory**. It re-opens a durable store, verifies integrity, and
> reports where a workflow stopped and whether its artifact is stale — with **no
> external call and no automatic transition**. The caller decides what happens
> next. Recovery is **not** execution reconciliation and never resumes an external
> side effect. `execution_status` stays `DISABLED`.

Machine-readable companion: `docs/recovery_statuses.json`.

## What recovery does

`recover_workflow(store, tenant_id, revision_id, current_identity=None)` (exposed
as `CodeGovernanceService.resume_workflow`):

1. loads the `workflow_index` pointer for the revision (fail closed if absent),
2. verifies record fingerprints and the event-chain linkage,
3. reads the immutable last committed state,
4. optionally compares a caller-supplied current identity (repo/base/head) to the
   persisted change identity to detect staleness,
5. returns a structured `RecoveryResult`.

No network client is constructed. No workflow transition is performed. The store
is not written to.

## Recovery vocabulary

| Status | Meaning | Requires explicit action |
|---|---|---|
| `RECOVERED_COMPLETE` | reached a terminal complete state (`SHADOW_COMPLETE`) | no |
| `RECOVERED_PENDING` | stopped mid-workflow; forward progress is possible | **yes** |
| `RECOVERED_STALE` | a newer head supersedes the persisted artifact | **yes** |
| `RECOVERED_BLOCKED` | stopped at a fail-closed terminal (blocked/incomplete/error) | no |
| `INCOMPLETE_TRANSACTION_ROLLED_BACK` | a stage was rolled back; no partial state exists | no |
| `INTEGRITY_FAILURE` | a recomputed fingerprint or chain link did not match | no |
| `SCHEMA_INCOMPATIBLE` | the store schema is unsupported | no |
| `REFERENCE_MISSING` | the revision is not present in the store | no |
| `TENANT_MISMATCH` | a cross-tenant record/linkage was found | no |

`RecoveryResult.requires_explicit_action` is `True` only for `RECOVERED_PENDING`
and `RECOVERED_STALE`.

## Why no auto-resume

The shadow product coordinates but owns no authority and executes nothing. Even
if a workflow stopped mid-stage, there is no external effect to "finish". Auto-
transitioning on restart would risk re-deriving governance state from a possibly
stale artifact without a human or an authorized actor in the loop. So recovery
reports and stops; continuation is an explicit, caller-driven step against a
freshly verified artifact.

## Staleness without a network

Staleness is detected by comparing a **caller-supplied** current identity to the
persisted change identity — never by calling GitHub. This keeps recovery fully
offline and deterministic while still flagging that a chain's head SHA has been
superseded.
