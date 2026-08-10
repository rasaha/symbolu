# Live-State Audit — Policy Workflow Compiler P2

Semantic Workflow Enrichment, Role-Relevant Contract Extraction, Dependency
Preservation and Versioned Release Validation.

## Repository state at branch creation

| Item | Value |
|---|---|
| Repository | `rasaha/symbolu` |
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default-branch tip / starting commit | `c9b630ba91fa382f9b21f61fce4e8fbca2812ac4` |
| Working branch | `claude/policy-workflow-compiler-p2` (env `claude/` prefix; supersedes suggested `chatgpt/policy-workflow-compiler-p2`) |
| Working tree at branch creation | clean |
| Active compiler P2 PR already open? | **No** |

## Prerequisite PRs (verified merged)

| PR | What | State | Merge commit |
|---|---|---|---|
| #1303 | Policy Workflow Compiler **P1** | merged | `e2d82ab4dc18d5cc816adf6c27263f8ad9f77b3f` |
| #1308 | Agent Workforce Composer **P1** | merged | `d1cfad24777ae0bbd49f7be4a699786fed1ffb3b` |
| #1310 | Agent Workforce Composer **P2** | merged | `0f5a461fb6714a4c55637d29e488814a2fe1a646` |
| **#1312** | **Governance Studio P3A** | **merged** | `8f19d17bba08864af81b2369aacf8102dea3a582` (verified via GitHub: `merged=true`, base = default branch, merged_at `2026-08-03T15:59:22Z`) |

Gate **PWC-P2-A1** (live prerequisites) is satisfied: PR #1312 is verified merged and
its merge commit is recorded. The P3A ownership document
(`apps/ugence-governance-studio/docs/COMPILER_VS_OVERLAY_OWNERSHIP.md`) is present on
the default branch and is the binding requirements source for this phase.

## Compiler package under change

| Item | Value |
|---|---|
| Package (import) | `ugence_policy_workflow_compiler` |
| Distribution | `ugence-policy-workflow-compiler` |
| Location | `packages/tooling/policy-workflow-compiler/` |
| Version (before) | `0.1.0` |
| Core dependency | `pydantic>=2` (stdlib + pydantic only; leaf package, no Ugence imports) |
| Public API surface (before) | **71 names**, frozen in `artifacts/public_api.json` |
| Source size (before) | ~5,786 lines |

## Baseline verification (before any change)

| Gate | Result |
|---|---|
| Compiler P1 test suite (`pytest tests/`) | **78 passed, 1 skipped** |
| Compiler isolated-distribution verifier | **PASS** (wheel bit-for-bit reproducible) |
| Compiler public-API snapshot vs frozen artifact | **in sync (71 names)** |
| AWC P1/P2 (downstream consumer, unchanged) | **158 passed** |
| Governance Studio P3A fixtures (downstream, unchanged) | **94 passed** |
| Platform-freeze verification | **PASS** — digest `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |

## Change discipline for P2

- **Additive only.** P2 enrichment is a new, parallel `workflow_ir.v2` layer plus new
  public API/CLI surface. The existing `workflow_ir.v1` emission path is **not
  modified**, so v1 canonical serialization and P1 fingerprints stay byte-stable by
  construction.
- **Outside the compiler package**, P2 touches only its own audit directory
  (`docs/audits/policy_workflow_compiler_p2/`) and a scoped CI workflow — no frozen
  governance artifact, no `platform/` manifest, no AWC/Governance Studio source. The
  platform-freeze digest must remain `d993093570…` after the change.
- **No downstream churn.** The AWC compiler adapter and the Governance Studio P3A
  fixtures/expected outputs are **not** modified in this PR (that is the next phase,
  AWC P2.1).
