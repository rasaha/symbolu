# Code Governance Application Mapping

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Maps the four closed prerequisites onto the
first Code Governance profile (`github_exact_merge`,
`docs/design/action_clearance/GITHUB_MERGE_PROFILE.md`), for **direct** and **squash** merge only.
Rebase and merge queue stay out of the first enforcement profile (they are deferred / Phase I in the
merged design).

## End-to-end flow

```text
GitHub + enterprise sources
      ↓ signal adapters normalize → TrustedSignal (with SignalProvenance, Level 1+)
Action Clearance request (ClearanceRequest, github_exact_merge profile)
      ↓ deterministic evaluator
ClearanceResult (CLEAR/HOLD/BLOCK/ESCALATE)
      ↓ Workflow Service persists
ClearanceReceipt (receipt_id = acr_<result_fingerprint>, lifecycle ISSUED)
      ↓ execution boundary
reserve_once(execution_key, clearance_receipt_ref, expected_authorization_ref, expected_action_fingerprint, ttl)
      ↓ ACQUIRED
GitHub execution provider (ExternalExecutionProvider.dispatch → merge)
      ↓
ExecutionObservation → ReconciliationRecord
```

## Direct merge & squash merge

| Aspect | Direct merge | Squash merge |
|---|---|---|
| **trusted signal producers** | GitHub adapter (`base_sha`, `head_sha`, `expected_merge_tree`, `required_checks`, `approval_state`), identity provider (`actor_state`), change-mgmt (`active_freeze_state`), incident system (`active_incident_state`), execution ledger (`authorization_consumption_state`), policy authority (`policy_version`) | same set; `expected_merge_tree` is the squash-result tree |
| **receipt lineage key** | `(tenant_id, authorization_ref, authorized_action_fingerprint, target_ref=repo+branch, profile_id=github_exact_merge)` | same tuple; `authorized_action_fingerprint` differs because `merge_method=squash` folds into it |
| **execution key** | `(tenant_id, authorization_ref, authorized_action_fingerprint, target_ref, operation=merge)` | same shape; distinct fingerprint |
| **reservation operation** | `operation = merge` (direct) | `operation = merge` with squash-bound fingerprint |
| **invalidation events** | head SHA changed (`GITHUB_HEAD_SHA_CHANGED`), base advanced (`GITHUB_BASE_ADVANCED`), merge tree mismatch, method changed, approval withdrawn, required check failed, freeze/incident active, authorization consumed | same, plus squash-tree mismatch |
| **reconciliation result** | observe GitHub merge outcome; `SUCCEEDED`/`FAILED`/`DUPLICATE`; unknown → reconcile before any retry | same |

## Why merge method matters to identity

Direct vs squash produce **different resulting trees**, so they are **different authorized actions** —
`merge_method` folds into `authorized_action_fingerprint`. A clearance for a squash never authorizes a
direct merge, and vice versa. This is why `merge_method` is carried but not a separate key field
(`EXECUTION_KEY.md`): it is already inside the action fingerprint.

## Excluded from the first enforcement profile

- **Rebase:** `NO_SUPPORT_IN_MVP` (no deterministic pre-merge exact-tree binding) — a rebase request →
  `UnsupportedProfileError`, never a silent CLEAR.
- **Merge queue:** Phase I. The original PR clearance never auto-authorizes a changed `merge_group_sha`;
  a regenerated merge group is a **new lineage** requiring a new authorization and clearance
  (`GITHUB_MERGE_GROUP_MISMATCH`).

## What must exist for enforced direct+squash merge

1. GitHub + enterprise signal adapters emitting Level-1 provenance (Prereq A) — **shadow-integration**.
2. Durable `ClearanceReceiptRepository` in the Workflow Service (Prereq B) — **enforcement**.
3. Receipt lifecycle + invalidation wiring (Prereq C) — **enforcement**.
4. Atomic `reserve_once` durable backend + GitHub provider dispatch/observe/reconcile (Prereq D) —
   **enforcement** (the P0 gate for enforced merge).

## Closure

The mapping is complete for direct+squash. Prerequisites A–C are closed at the interface level; D's
contract is closed and its durable backend is the enforced-merge blocker.
