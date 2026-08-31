# Agent Workforce Composer — Phase 0 Live-State Audit

**Audit phase:** `AWC_PHASE0_H16_RECONCILIATION`
**Audit date:** 2026-08-03
**Repository:** `rasaha/symbolu`

This file records the verified live state of the repository at the moment Phase 0
reconciliation work began. Every value here was resolved from current code, git
history, and merged pull requests — not from memory or the merged AWC narrative.

## Git baseline

| Fact | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default branch tip / starting commit | `0d8c4e05718494e95c501402dd5b09daefc99636` |
| Working branch (this phase) | `claude/awc-phase0-h16-reconciliation-b7jw0x` |

> **Branch-name note.** The AWC roadmap suggested `chatgpt/awc-phase0-reconciliation`.
> This execution environment mandates the `claude/` prefix and the specific branch
> `claude/awc-phase0-h16-reconciliation-b7jw0x`. The mandated branch is used and
> the suggested name is recorded here as superseded.

## Merged pull requests (verified via GitHub API + git history)

### PR #1303 — Policy Workflow Compiler MVP

| Field | Value |
|---|---|
| Title | tooling: implement structured Policy-Pack workflow compiler MVP |
| State | `closed` / **merged = true** |
| Merged at (UTC) | 2026-08-03T11:27:48Z |
| **Merge commit** | `96afb58a5792b4d80225f81406abf8fcfe0eec4f` |
| Head ref / sha | `claude/policy-workflow-compiler-mvp-5m6o02` / `4a95d538270b9e88a75f67e382600a63d4d82c62` |
| Base ref | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Size | +11,275 lines, 109 files, 13 commits |
| URL | https://github.com/rasaha/symbolu/pull/1303 |

### PR #1305 — Agent Workforce Composer design spec

| Field | Value |
|---|---|
| Title | Add Agent Workforce Composer design specification (spec-only) |
| State | `closed` / **merged = true** |
| Merged at (UTC) | 2026-08-03T11:39:51Z |
| **Merge commit** | `0fa80fe4146478aa452ae40eed12e234683e645e` |
| Head ref / sha | `claude/agent-workforce-composer-spec-3rjaux` / `b80e8104786cbd8c9729df3a8fb14ef993b19bd3` |
| Base ref | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Size | +1,828 lines, 7 files, 1 commit |
| URL | https://github.com/rasaha/symbolu/pull/1305 |

Both PRs are merged into the default branch and are reachable from the starting
commit (`git log` confirms `96afb58a` and `0fa80fe4` on the default branch, with
PR #1305 layered on top of PR #1303's merge commit).

## Policy Workflow Compiler — implemented state (contradicts "spec-only")

The compiler is **implemented**, not spec-only. Verified from source:

| Fact | Value |
|---|---|
| Package root | `packages/tooling/policy-workflow-compiler/` |
| Distribution | `ugence-policy-workflow-compiler` |
| Namespace | `ugence_policy_workflow_compiler` |
| Supported import surface | `ugence_policy_workflow_compiler.api` |
| Distribution / product version | `0.1.0` / `0.1.0` |
| Public API name count | **71** (frozen `artifacts/public_api.json`) |
| WorkflowIR version | `workflow_ir.v1` |
| Policy pack schema version | `policy_pack.v1` |
| Capability registry version | `capability_registry.v1` |

Honest maturity booleans (from `version.py::version_info()`):

- `structured_policy_pack_implemented = True`
- `deterministic_compilation_verified = True`
- `procurement_reference_equivalence_verified = True`
- `document_extraction_implemented = False`
- `runtime_deployment_implemented = False`
- `pilot_validated = False`
- `production_certified = False`

**Consequence:** the AWC design documents' description of the compiler as
"spec-only" / to be integrated "when it ships" / lacking a typed `WorkflowIR` is
**stale and must be corrected**. The compiler emits a typed, deterministic
`WorkflowIR` today. See `STALE_ASSUMPTION_INVENTORY.md` and
`POLICY_COMPILER_CONTRACT_AUDIT.md`.

## Platform freeze (verified read-only)

| Fact | Value |
|---|---|
| Command | `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` |
| Result (before edits) | **PASS** |
| Substantive digest (before) | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |
| Re-baselined? | No — verification is read-only; no snapshot regenerated |

This digest is the "before" value. Because Phase 0 adds only documentation,
audit artifacts, an ADR, and doc-validation scripts — and does not touch any
frozen source module or public API — the digest must be **unchanged** after the
phase. See the completion report for the "after" value.

## H16 coordination layer under audit

| Module | Purpose (pre-audit) |
|---|---|
| `agentic/agentic_framework/coordination.py` | Agent coordination / selection / delegation concepts (H16) |
| `agentic/agentic_framework/multi_agent.py` | Multi-agent orchestration / routing (H16) |

Full symbol inventory and dispositions: `H16_OVERLAP_INVENTORY.md` / `.json`.

## Mandated term-search summary (repo-wide)

Counts of Python files referencing key identifiers (evidence that these concepts
already exist in live code, which is why reconciliation — not green-field
invention — is required):

| Identifier | `.py` files referencing |
|---|---|
| `WorkflowIR` | 10 |
| `AgentProfile` | 20 |
| `CapabilityRegistry` | 34 |
| `DelegationContract` | 4 |
| `AgentAssignment` | 2 |
| `assigned_agent` | 10 |
| `authority_scope` | 18 |

`WorkflowGraphSource` appears only inside the AWC design documents (4 docs) — it
is an AWC-proposed concept, **not** a live compiler type; the live type is
`WorkflowIR`. This is a semantic-drift finding (see `STALE_ASSUMPTION_INVENTORY.md`).
