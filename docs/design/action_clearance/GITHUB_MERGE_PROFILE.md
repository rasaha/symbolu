# GitHub Exact-Merge Clearance Profile (first profile)

The first product profile, for Code Governance. It binds the artifact, not just the source SHA —
matching `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` §4.6 (Bind the governed artifact — P0) and §4.7 (prove
the chain — P0).

`profile_id = github_exact_merge`.

## Binding set

| Field | Binds |
|---|---|
| `repository_ref` | repository identity |
| `org_ref` / `installation_ref` | organization / installation identity |
| `pull_request_ref` | pull-request identity |
| `base_sha` | target/base SHA |
| `head_sha` | source/head SHA |
| `merge_method` | `merge` / `squash` / `rebase` / `merge_queue` |
| `expected_merge_tree` | the exact resulting tree |
| `merge_group_sha` | merge-group artifact (queue only) |
| `target_branch` | target branch |
| `required_checks` | required-check set |
| `approval_state` | current approvals |
| `actor_state` | actor status |
| `policy_version` | policy version |
| `active_freeze_state` | change-freeze state |
| `active_incident_state` | incident state |
| `authorization_consumption_state` | prior-consumption |

These populate the CER `permitted_parameters` / `required_controls` and the product
`ExactChangeAuthorization` envelope (a Code Governance product concept), and become
`ActionIdentity` + profile signals in the `ClearanceRequest`.

## Required signals by merge method

### Direct merge commit — MVP ✅

- base/head identity unchanged (`base_sha`, `head_sha`),
- expected merge tree unchanged (`expected_merge_tree`),
- required checks current & green,
- approvals current,
- no active freeze / incident,
- authorization unused (`PRIOR_CONSUMPTION` = free),
- target available.

### Squash merge — MVP ✅

- exact resulting tree binding (`expected_merge_tree` of the squash result),
- current head/base,
- method unchanged (`merge_method == squash`).

### Rebase merge — DEFERRED (no MVP support)

Rebase re-writes commits onto the base; a deterministic **exact resulting tree** cannot be bound
pre-merge in MVP without executing the rebase server-side. Disposition: **NO_SUPPORT_IN_MVP**, revisited
in Phase I after exact-artifact behavior is proven for direct/squash. Until then a rebase request →
`UnsupportedProfileError` (a `NON_RETRYABLE_ERROR`), never a silent CLEAR.

### Merge queue — Phase I

```text
original PR authorization
  → merge-group generation (GitHub creates merge_group_sha)
    → new merge-group evidence (required checks re-run against the group)
      → derived exact-action authorization (a NEW ActionGate authorization for the group artifact)
        → Action Clearance on the merge-group identity (clears merge_group_sha, not head_sha)
```

The original PR clearance **never** auto-authorizes a changed merge-group artifact: a different
`merge_group_sha` yields a different `authorized_action_fingerprint`, which requires a new clearance
(`GITHUB_MERGE_GROUP_MISMATCH` if the presented group differs from the cleared one).

## Profile reason codes

`GITHUB_HEAD_SHA_CHANGED`, `GITHUB_BASE_ADVANCED`, `GITHUB_MERGE_TREE_MISMATCH`,
`GITHUB_MERGE_GROUP_MISMATCH`, `GITHUB_MERGE_METHOD_CHANGED`, `GITHUB_TARGET_BRANCH_MISMATCH`,
`GITHUB_REQUIRED_CHECK_PENDING`, `GITHUB_REQUIRED_CHECK_FAILED`, `GITHUB_APPROVAL_WITHDRAWN` — all
`PROFILE_SPECIFIC` in [`STATUS_AND_REASON_SEMANTICS.md`](STATUS_AND_REASON_SEMANTICS.md).

## No GitHub client in the core

The profile defines *which signals are required and how they map to core reason codes*. The actual
GitHub API calls live in a GitHub **signal adapter** that produces normalized `TrustedSignal`s; the
neutral evaluator holds no GitHub client. Schema:
[`github_merge_profile.schema.json`](github_merge_profile.schema.json).
