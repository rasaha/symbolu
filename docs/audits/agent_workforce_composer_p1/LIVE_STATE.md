# Live-State Audit — Agent Workforce Composer P1

Recorded before any code change (`git` + GitHub MCP).

| Item | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `913300210e639df96b4c5123297221dcdb4b3c59` |
| Working branch | `claude/agent-workforce-composer-p1-54g1d0` |
| PR #1303 | **merged** — merge commit `96afb58a5792b4d80225f81406abf8fcfe0eec4f` (Policy Workflow Compiler MVP) |
| PR #1305 | **merged** — merge commit `0fa80fe4146478aa452ae40eed12e234683e645e` (AWC design spec) |
| PR #1306 | **merged** — merge commit `913300210e639df96b4c5123297221dcdb4b3c59` (Phase 0 H16 reconciliation) |
| Platform-freeze digest (before) | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |
| AWC package already present? | **No** — `packages/capabilities/agent-workforce-composer/` did not exist |
| Active P1 PR already open? | **No** |

The starting commit is PR #1306's merge commit on the default branch, so the
working branch descends from a tip that contains PRs #1303, #1305 and #1306.

## Binding Phase 0 inputs
- ADR: `docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md` — Option A.
- Frozen boundary contract: `docs/architecture/agent_workforce_composer_boundaries.json`.
- Phase 0 audit set: `docs/audits/agent_workforce_composer_phase0/`.

## Live compiler contract
`ugence_policy_workflow_compiler` (namespace) exposes `WorkflowIR` (`workflow_ir.v1`)
with **14 node kinds** and **9 edge kinds**; `CompiledReleasePackage` /
`ReleaseManifest` / `CapabilityManifest`; `AuthorityDisposition`
(ADVISORY/AUTHORITATIVE) and `CapabilityId` (TAP, DECISION_AUTHORITY, ACTION_GATE,
ACTION_CLEARANCE, STORYGRAPH, MODEL_SELECTION, OPTIONAL_ORCHESTRATOR, COMPILER).
