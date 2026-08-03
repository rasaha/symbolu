# Permission Proposal View Design

**Screen:** `src/features/permissions/PermissionScreen.tsx` ·
**Route:** `/scenarios/:id/permissions` · **Operation:** `get_scenario_plan`
(reads `permission_proposals`).

## Intent

Display the backend's **proposed** permission scope for each assigned role —
categorised, with feasibility and human-review flags — while making unmistakably
clear that the Studio proposes and never grants.

## Rendering rules

- Each proposal shows `role_id`, its `categorized_permissions[]` grouped by
  `category`, and the `feasible` / `requires_human_review` flags.
- A prominent notice (`data-testid="proposal-notice"`) reads that these are
  proposals the Studio surfaces for human review and that it does **not grant,
  provision or activate** any permission. Proposed scopes render with the
  "permission proposed" semantic token; excluded/prohibited entries use the
  "permission excluded" token.
- Every scope entry is labelled "Proposed" — never "granted", "provisioned",
  "authorized" or "active".

## Terminology boundary (§19)

This view is the reason P3C's blanket ban on "permission proposal" language was
lifted: proposals are legitimate P3D content. What remains banned everywhere in
`src/` — enforced by `scripts/verify-terminology.mjs` and
`tests/permission-scope.test.tsx` — is any grant/provisioning/authorization phrasing
("permission granted", "grant permission", "provision permission",
"runtime provisioning", "access granted", "authorized to execute", …). The Studio
performs no authorization action of any kind.
