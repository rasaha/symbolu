# Agent Runtime — Post-Merge Fidelity & Governance-Safety Audit

**Scope:** bounded post-merge correction of `ugence-agent-runtime` after PR #1287 merged.
This is **not** an H22 phase. It records the live starting point and the corrections
required before H22 or the Governance Contracts extraction proceed.

## Live starting point (verified)

| Fact | Value |
| --- | --- |
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Merge commit | `25c6c815` (Merge pull request #1287) |
| Package path | `packages/runtime/agent-runtime/` |
| Namespace / distribution | `ugence_agent_runtime` / `ugence-agent-runtime` |
| Version | `0.1.0` |
| Legacy runtime | `agent_runtime_migration/` (unchanged, intact) |
| Real consumers of new package (outside itself) | **0** |
| Real consumers of legacy runtime (outside itself) | **0** |
| Agent Runtime CI workflow | **none** (only `terminology-ci` touched the merged head) |
| Package suite / isolated-install in CI | **not enforced** |

## Finding 1 — this was NOT a behavior-preserving migration

The two runtimes are structurally different implementations, both present in the repo:

**Legacy `agent_runtime_migration.runtime.runtime.AgentRuntime`** — a *proposer loop*:

```
AgentRuntime(*, executor, planner=Planner(), reflector=Reflector(), memory=EpisodicMemory())
    .run(goal: Goal, *, run_id, max_replans, resolution_budget) -> RunOutcome
# Goal → Plan → Action → ExecutionResult → Observation → Memory → Reflection → continue/retry/replan/human/stop
```

Owns: planning, action selection, episodic memory, reflection, resolution budget, replan.

**New `ugence_agent_runtime.runtime.engine.AgentRuntime`** — a *coordination kernel*:

```
AgentRuntime(config: AgentRuntimeConfig)
    .start_workflow(definition) / resume / pause / cancel / recover
# Workflow → Task(dependency order) → governance → provider → checkpoint
```

Owns: workflow/task lifecycle, provider invocation, retry/timeout/cancellation,
checkpoints, recovery, events. **Explicitly excludes** planning, reasoning, memory.

**Conclusion:** the new package is a newly created execution-coordination kernel, not a
relocation of the established proposer. Prior claims of "runtime behavior preserved" and
"no duplicate implementation" are inaccurate and are corrected in this phase.

## Finding 2 — the default governance behavior is fail-open (P0)

`TaskDefinition.consequential` defaults to `True`; `AgentRuntimeConfig()` installs
`NoopGovernanceHook`, which returns `CLEAR` for every transition. Verified live:

```
AgentRuntimeConfig() + consequential task + registered provider  ->  provider EXECUTED, workflow COMPLETED
```

Operationally the runtime treats its own default as permission to execute a consequential
transition. This contradicts the canonical Ugence separation. **Corrected** (P0-1): the
default hook fails closed (`UnconfiguredGovernanceHook` → BLOCK); an always-CLEAR hook is
retained only as an explicitly named, opt-in, documented-unsafe testing helper.

## Finding 3 — exact-action governance binding is incomplete (P0)

The merged boundary passes `operation` + mutable `arguments` and records an *optional*
`evaluation_reference`. It does not construct an immutable proposal, does not require a
proposal fingerprint, does not bind CLEAR to an exact invocation, does not require a
non-empty reference for CLEAR, and does not validate `valid_until` before invocation.
**Corrected** (P0-2): a neutral immutable `TransitionProposal` with a deterministic
fingerprint is constructed before evaluation and bound to the exact provider invocation;
the runtime fails closed on missing/unknown/mismatched/expired/unreferenced results.

## Finding 4 — the compatibility proof does not test legacy compatibility (P0)

`ugence_agent_runtime.compat` aliases (`Runtime → AgentRuntime`, `Workflow →
WorkflowDefinition`, …) are aliases **inside the new package**; the merged tests only
proved those new aliases point at new objects. They did not import the actual legacy path
`agent_runtime_migration.runtime.runtime.AgentRuntime`, which is a *different*
implementation with an incompatible API. **Corrected** (P0-3, Outcome B — honest
coexistence): false identity claims removed; a migration map + fidelity matrix published;
a real test imports the legacy path and asserts coexistence (skipped in isolated-wheel
context where the monorepo is absent).

## Finding 5 — package tests are not CI-enforced (P0)

The only workflow attached to the merged head is `terminology-ci` (terminology + doc
links + platform-freeze). The package suite and isolated-install verifier are offline
results only. **Corrected** (CI): a scoped `agent-runtime-ci` workflow is added.

## Canonical architecture decision

Retain `ugence-agent-runtime` as the **execution-coordination kernel** (owns workflow/task
lifecycle, provider invocation, retry/timeout/cancellation, checkpoints/recovery, events,
immutable transition-proposal construction, and consumption+validation of externally
produced governance permission). It does **not** own planning, reasoning, memory, model
selection, policy, authorization, clearance, or sequence-risk policy.

`agent_runtime_migration` is classified as a **legacy agentic proposer + concrete
governance-integration assembly**, not the compatibility implementation of the kernel. It
is retained (not deleted). `ugence-agentic-framework` is **not** created in this phase.

## Maturity classification

`IMPLEMENTED_AND_OFFLINE_VERIFIED` → after this phase, with a scoped CI workflow added.
It is **not** live-verified, pilot-validated, enforcement-ready, or production-ready.
