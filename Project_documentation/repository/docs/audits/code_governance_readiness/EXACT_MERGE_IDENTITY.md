# Exact Merge-Artifact Identity — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4.6).
> Machine-readable form: `merge_identity_schema.json`.

The approved **source** SHA alone is insufficient: the code that lands can differ from what was
reviewed when the base advances, or GitHub creates a merge commit / squash / rebase / merge-group.
The governed operation must bind the exact artifact.

## 1. Identity model per merge mode

**Direct merge commit** — `repository · base_sha · head_sha · merge_method=merge ·
expected_merge_tree_digest → resulting merge commit`. Exact preauthorization: **SUPPORTED**.

**Squash merge** — `repository · base_sha · head_sha · merge_method=squash ·
expected_resulting_tree → resulting commit`. Exact preauthorization: **SUPPORTED**.

**Rebase merge** — GitHub rewrites commits, so per-commit SHAs are not knowable before merge. The
expected resulting **tree** can be computed and bound; the rewritten commit ids are reconciled
after the fact. MVP classification: **SUPPORTED_WITH_ADDITIONAL_RECONCILIATION** (bind the tree,
reconcile commit ids post-merge). If the tree cannot be reliably pre-derived for a given repo,
degrade rebase to **recommendation-only** for that policy scope. Not exact-commit-SHA
preauthorizable.

**GitHub merge queue** — two-step:
```
Authorize queue entry
  → GitHub creates merge-group SHA
    → Validate merge group (re-run required checks against it)
      → ACP clears the exact merge-group artifact
        → Execute / allow queue merge
          → Reconcile resulting commit
```
The **original PR `DecisionRecord` remains the binding decision**, but a **derived authorization**
(a new CER + `ActionGovernanceRequest` bound to `merge_group_sha`) is required for the merge-group
artifact, because the artifact identity changed. See `MERGE_QUEUE_ANALYSIS.md`.

## 2. How the identity is carried (no neutral-contract change)

- **Values** → `ActionRequest.requested_parameters` (`dict[str,str]`) and neutral
  `ActionGovernanceRequest.requested_parameters` (`Mapping[str,str]`).
- **Permitted parameter names + required controls** → CER `permitted_parameters` /
  `prohibited_parameters` / `required_controls` (`tuple[str,...]`).
- **Decision / tenant / policy / expiry / content hash** → CER typed fields.
- **Integrity over the values** → the product `ExactChangeAuthorization` envelope content hash +
  `ActionGovernanceResult.fingerprint`.

The identity tuple is **PRODUCT_INTERNAL** (see `merge_identity_schema.json`). No CER/ActionGate
schema change is required for MVP (see `DECISION_AND_CER_MAPPING.md` §6).

## 3. Invalidation rules

| Event | Effect |
|---|---|
| new commit pushed | INVALIDATE (head SHA changed) → re-enter validation |
| force push | INVALIDATE (head/base changed) |
| base branch advanced | INVALIDATE if merge base moved → re-validate merge tree |
| policy changed | INVALIDATE (policy_version mismatch) → re-decide |
| required check changed | INVALIDATE required-check set → re-validate |
| approval dismissed | INVALIDATE authority basis → re-approve |
| merge method changed | INVALIDATE (bound parameter changed) → re-authorize |
| merge-group regenerated | INVALIDATE derived authorization → re-validate + re-clear |
| authorization expired | AUTHORIZATION_EXPIRED (CER `expires_at` / envelope expiry) |
| incident / freeze activated | BLOCK at ACP clearance → CLEARANCE_DENIED |

**Enforcement note:** these invalidations are **not automatic** in Decision Authority (no patch-hash
watcher). The **Workflow Service must implement them** as re-entry triggers (design §7 re-entry rule)
and re-verify the merge identity at ACP clearance time to catch races.

## 4. Proposed identity tuple (summary)

See `merge_identity_schema.json` for the full machine-readable tuple:
`repository, pull_request, source_head_sha, base_sha, target_branch, merge_method,
expected_merge_tree_digest, expected_result_commit, merge_group_sha, required_check_set,
policy_version, decision_record_id, cer_id, cer_content_hash, authorization_expiry,
authorization_single_use`.
