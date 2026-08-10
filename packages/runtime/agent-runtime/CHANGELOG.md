# Changelog — ugence-agent-runtime

All notable changes to the independent Agent Runtime distribution are recorded here.
This project follows semantic versioning for the distribution.

## 0.3.0 — H22-A bounded workflow advancement

Adds a small, additive, deterministic seam that lets an external orchestrator create a
workflow **without draining it to completion** and then advance it **one bounded quantum
at a time** to a stable, checkpointed boundary. This is the compositional foundation the
future H22 portfolio scheduler needs in order to interleave independent workflows fairly
(`advance(A)`, `advance(B)`, `advance(A)`, …). Additive only — no change to exact-action
fingerprint semantics, governance ownership, canonical execution state, checkpoint digest
semantics, or recovery behavior. **This is H22-A, not full H22:** no portfolio, no
cross-workflow dependencies, no priority/fairness/aging, no shared budget, no concurrency.

### Added
- **`AgentRuntime.prepare_workflow(...)`** (and the `prepare_workflow(runtime, …)`
  convenience function) — create and register a workflow instance with the exact same
  setup `start_workflow` performs (instance creation, `WORKFLOW_CREATED` /
  `WORKFLOW_STARTED`, and the initial `RUNNING` checkpoint) but **without driving any
  task**. No provider or governance call happens at preparation. A prepared instance
  persists as an ordinary `RUNNING` checkpoint, so its recovery semantics are the existing
  ones (recovered as `PAUSED`, requiring explicit continuation — never auto-run).
- **`AgentRuntime.advance_workflow(instance_id)`** (and `advance_workflow(runtime, …)`) —
  advance a prepared/running workflow by **one bounded quantum**: *at most one runtime task
  transition through one stable, checkpointed boundary*. Concretely a quantum is one of:
  one task run through the full governance→exact-action→provider→transition→checkpoint
  chain; one finalization (`→ COMPLETED`, or all remaining work blocked `→ WAITING`); or
  one cancellation. The chain runs **entirely within** the quantum, so the scheduler can
  never observe or preempt a workflow between a governance `CLEAR` and the provider
  invocation it cleared. On a non-`RUNNING` workflow it is a deterministic no-op that
  reports why (`ALREADY_TERMINAL`, or `REQUIRES_RESUME` for a `WAITING`/`PAUSED` workflow
  — bounded advancement never self-resolves a governance `HOLD`/`ESCALATE`).
- **`WorkflowAdvanceOutcome`** — a frozen, read-only value object returned by
  `advance_workflow`: `instance_id`, `workflow_id`, `status_before`/`status_after`,
  `stop_reason`, `progressed`, `task_id`, `task_status`, `execution_state_digest`,
  `checkpoint_digest`, and `terminal`/`waiting`/`paused` flags. It references
  runtime-owned canonical execution state and the emitted checkpoint **by digest** rather
  than duplicating either — the runtime remains the sole owner of execution-trajectory
  truth. `to_dict()` provided.
- **`WorkflowAdvanceStop`** — a stable `str` enum of the boundaries a quantum may stop at
  (`TASK_ADVANCED`, `WORKFLOW_COMPLETED`, `WORKFLOW_FAILED`, `WORKFLOW_WAITING`,
  `WORKFLOW_PAUSED`, `WORKFLOW_CANCELLED`, `ALREADY_TERMINAL`, `REQUIRES_RESUME`).

### Changed
- **`start_workflow` is now implemented on top of the new primitive** (`prepare_workflow`
  followed by repeated bounded advancement until the existing stopping condition). Its
  externally observable behavior — event stream, checkpoints, and terminal/HOLD/ESCALATE
  results — is unchanged; a regression test asserts the event sequence is byte-identical
  to `prepare_workflow` + drive.

### Unchanged (explicitly)
- No new event types; the existing deterministic event stream is preserved. Exact-action
  proposal binding, canonical execution state, checkpoint digest semantics, and
  side-effect-free recovery are all untouched. No concurrency, threads, asyncio, portfolio
  scheduler, cross-workflow dependencies, priority/fairness, shared budget, agent
  selection, shared reasoning memory, or Runtime Assurance were introduced.

## 0.2.0 — canonical execution state

Establishes the Agent Runtime as the canonical owner of **execution-trajectory
identity**: a deterministic, versioned, integrity-protected, runtime-owned snapshot of
what execution trajectory is being coordinated, what caused it, what immutable action
identity is involved, and which external authority/artifact references are associated.
Additive only — no change to exact-action fingerprint semantics, governance ownership,
task scheduling, retries, timeout, cancellation, recovery behavior, or the digest
semantics of existing serialized checkpoints. Not H22, not Runtime Assurance, not an AWC
adapter beyond a minimal neutral lineage seam.

### Added
- **`CanonicalExecutionState`** (`models/execution_state.py`) — a frozen, stdlib-only
  dataclass with deterministic canonical serialization and a SHA-256 `state_digest`
  (excludes itself; identity-bearing changes change the digest; semantically equal
  construction yields an identical digest). Flat, typed identity fields only — it
  references the active proposal by `proposal_fingerprint` and never re-canonicalizes the
  proposal's argument payload. `to_dict()`/`from_dict()`/`compute_digest()`/`sealed()`/
  `is_intact()`.
- **`ExecutionLineage`** — a typed, optional, neutral seam for causation / parent /
  agent-plan / artifact *references* (never untyped metadata; never fabricated; defaults
  to unavailable). Agent references are lineage constraints only — carrying one never
  causes the runtime to select or re-rank an agent. Supplied at **two levels**:
  workflow-common lineage (`start_workflow(lineage=…)`) and **per-task** lineage
  (`start_workflow(task_lineage={task_id: …})`, stored on `TaskInstance.lineage`).
  `overlay()` combines them so sibling tasks driven by different agents are attributed to
  their own agent/artifacts/causation while inheriting workflow-common references — the
  multi-agent case (Task 1 → Research, Task 2 → Risk, Task 3 → Execution).
- **Runtime derivation** (`runtime/execution_state.py`, `build_execution_state`) — the
  sole in-runtime author of snapshots, deriving them from config / instance / task /
  proposal / (optional) governance evaluation. Authority-lineage fields are copied
  verbatim from what governance returned and are `None` when governance produced nothing.
- **Read-only access** — `AgentRuntime.execution_state(instance_id, task_id=None)` and the
  `execution_state(runtime, …)` convenience function. No mutation API.
- **Trajectory journal** — every snapshot the runtime records (not only the latest per
  task) is retained by digest, so an `execution_state_digest` anchored on any earlier
  event stays resolvable via `AgentRuntime.execution_state_by_digest` /
  `execution_state_by_digest(runtime, …)`. The journal is persisted and restored across
  recovery.
- **Event anchoring** — `execution_state_digest=<digest>` added to `TASK_READY`,
  `GOVERNANCE_EVALUATION_REQUESTED`, `GOVERNANCE_DISPOSITION_RECEIVED`, `TASK_STARTED`,
  `PROVIDER_INVOKED`, `PROVIDER_COMPLETED`, `TASK_COMPLETED`, and `TASK_FAILED`. Digest
  references only — the full state is never stuffed into the event stream. No new event
  types; sequencing is unchanged.
- **Checkpoint lineage** — `Checkpoint` gains `checkpoint_version` (`"1"`), a
  self-verifying per-task `execution_states` section, the digest-keyed
  `execution_state_journal`, and the typed **lineage source** (`workflow_lineage` +
  `task_lineage`) preserved separately from historical snapshots so future snapshots after
  recovery keep the same references — including for tasks that had not yet run. The base
  coordination `digest` is computed over exactly the original payload, so pre-existing
  checkpoints verify byte-identically; a checkpoint deserialized without a version tag is
  treated as legacy `"0"` with lineage unavailable.
- **Versioned extension integrity boundary** — a second digest, `extension_digest`, covers
  the whole canonical-state extension (`checkpoint_version` + `execution_states` +
  `execution_state_journal` + `workflow_lineage` + `task_lineage`). The base `digest` is
  deliberately unchanged (legacy compatibility) and therefore does not cover the extension,
  so `extension_digest` is what protects the **lineage source** and the snapshot-collection
  **membership** — closing the gap where a tampered lineage source passed both the base
  digest and per-snapshot digests. Legacy (`"0"`) checkpoints carry no extension.
- **Strict cross-binding & consistency on recovery** — recovery rejects an unknown
  `checkpoint_version` (fail closed, never interpret a future schema under today's rules);
  for `"1"` it requires base digest + extension digest + cross-binding valid; for `"0"` it
  requires the base digest and no extension data. `validate_execution_states()` enforces,
  beyond each snapshot's own digest, that the map key equals the snapshot's own key field
  (task id / state digest), that instance/workflow/correlation identity match the
  checkpoint, that the referenced task exists, that the schema version is supported, that
  every latest snapshot is resolvable in the journal (latest↔journal consistency), and that
  the lineage source is structural (keys reference known tasks, values deserialize). An
  inconsistent canonical state fails closed with a precise reason — never silently accepted
  or discarded. Recovery restores the lineage source and journal
  (`RuntimeRecoveryResult.execution_states` / `.execution_state_journal`) and never
  fabricates missing references. **`runtime_id`/`runtime_version` on a snapshot are *origin*
  provenance** (the runtime that created that historical state) and are intentionally NOT
  required to equal the checkpoint writer, so recovery across a runtime upgrade — which is
  permitted with `config_mismatch=True` — yields a mixed-version journal that still recovers
  cleanly. Those fields stay integrity-protected by the snapshot's `state_digest` and the
  `extension_digest`.
- **Self-recoverability invariant** — the engine validates every checkpoint (base digest +
  extension digest + canonical-state binding) *before* persisting it, so the runtime never
  writes a checkpoint its own recovery validator would reject (fails closed with
  `CheckpointError` on an internal inconsistency instead of emitting an unrecoverable
  checkpoint).
- **Hardening** — unsupported `state_version` fails closed (`SUPPORTED_STATE_VERSIONS`);
  `valid_until` must be finite (NaN/Infinity rejected); digest serialization uses
  `allow_nan=False`.
- `ExecutionStateError`; canonical-execution-state test suite; docs
  `AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md`.

### Public API
- Added `CanonicalExecutionState`, `ExecutionLineage`, `execution_state`, and
  `execution_state_by_digest` to the curated surface; `start_workflow` gains optional
  `lineage=` and `task_lineage=` arguments (additive).

## 0.1.2 — exact-action contract hardening

Corrects three remaining gaps in the exact-action governance contract. Bounded
contract-hardening only — not H22, not a governance-integration phase.

### Changed (contract)
- **Deeply immutable proposal identity (A).** `TransitionProposal` arguments are now
  recursively frozen at construction (read-only mappings, tuples, frozensets); the
  proposal no longer retains caller-owned mutable structures by reference, and a hook
  cannot mutate proposal arguments. Unsupported argument types fail closed with
  `ProposalError` instead of relying on `repr()`. Provider-invocation arguments are
  re-materialized as a fresh mutable structure only after clearance validation.
- **Correlation is fingerprinted identity (B).** `compute_fingerprint` now includes
  `correlation_id`; changing only the correlation id changes the fingerprint. When a
  proposal carries a correlation id, a CLEAR result must echo it — missing
  (`GOVERNANCE_CLEAR_MISSING_CORRELATION`) or mismatched
  (`GOVERNANCE_CLEAR_CORRELATION_MISMATCH`) correlation fails closed. The provider
  invocation's correlation is revalidated in the exact-action re-fingerprint check.
- **Inclusive expiry (C).** Clearance is rejected when `now >= valid_until` (previously
  `now > valid_until`); at the exact expiry instant the clearance is expired.

### Added
- `ProposalError`; `TransitionProposal.materialize_arguments()`; contract-hardening test
  suite (immutability, correlation binding, inclusive expiry).
- CI workflow now also triggers on the default branch (path-filtered) so a merge that
  touches the package receives a recorded run.

## 0.1.1 — post-merge governance-safety & fidelity correction

Corrects issues found after 0.1.0 merged (PR #1287). This is a bounded correction
phase, **not** H22.

### Changed (governance safety)
- **Fail closed by default.** The default governance hook is now
  `UnconfiguredGovernanceHook`, which BLOCKs every consequential transition with reason
  `GOVERNANCE_NOT_CONFIGURED`. The previous default (`NoopGovernanceHook`, always CLEAR)
  was fail-open and is removed as a default.
- **Exact-action binding.** The runtime now constructs an immutable `TransitionProposal`
  with a deterministic fingerprint before evaluation, and the governance hook evaluates
  that proposal. A CLEAR result is honored **only** when it is bound to the exact
  proposal fingerprint, carries a non-empty binding reference, and is not expired; the
  provider invocation is re-fingerprinted immediately before the call. Any missing,
  mismatched, unreferenced, expired, or drifted binding fails closed.
- `GovernanceHook.evaluate(proposal, evaluation_time)` replaces the prior
  `evaluate(context, proposed_transition, evaluation_time)` signature.
- `GovernanceEvaluation` gains `proposal_fingerprint`, `authorization_reference`,
  `clearance_reference`; `valid_until` is now validated.

### Changed (honesty)
- **Compatibility reframed** as honest coexistence (Outcome B). The legacy runtime and
  the kernel are different implementations; the invented identity-preserving aliases and
  the "no duplicate implementation" claim are removed. `ugence_agent_runtime.compat` now
  offers a migration map + classification, not aliases.
- Documentation corrected: the package is described as a coordination kernel, not a
  behavior-preserving relocation; maturity is `IMPLEMENTED_AND_OFFLINE_VERIFIED`.

### Added
- `TransitionProposal` (+ `compute_fingerprint`), `UnconfiguredGovernanceHook`,
  `AllowAllGovernanceHook` (explicit, opt-in, unsafe), `validate_clearance`.
- Post-merge fidelity audit + fidelity matrix; governance-binding test suite; a scoped
  `agent-runtime-ci` GitHub workflow.

### Renamed / deprecated
- `NoopGovernanceHook` → `AllowAllGovernanceHook` (the old name remains as a deprecated
  alias that emits `DeprecationWarning`); never a default.

## 0.1.0 — first independent distribution

The Agent Runtime becomes an independently buildable and installable, domain-neutral
capability. This is a packaging and boundary-hardening release; no multi-workflow
orchestration (H22) is added.

> **Correction (see 0.1.1):** 0.1.0 described this as behavior-preserving with "no
> duplicate implementation." That was inaccurate — the package is a *new coordination
> kernel* that coexists with the legacy proposer. The 0.1.1 entry above supersedes those
> claims.

### Added
- Independent Python distribution `ugence-agent-runtime` (namespace
  `ugence_agent_runtime`), stdlib-only, `py.typed`.
- Curated public API (`ugence_agent_runtime.api`): `AgentRuntime`, `AgentRuntimeConfig`,
  workflow/task models, provider interfaces + registry, persistence interfaces +
  in-memory reference, neutral governance boundary, recovery, error taxonomy, and
  convenience functions.
- Neutral governance-integration boundary (`GovernanceHook`) with the established
  `CLEAR / HOLD / BLOCK / ESCALATE` vocabulary and a fixed, non-broadening mapping to
  runtime coordination behavior.
- Neutral provider/tool execution boundary (no vendor coupling).
- Deterministic workflow/task state machine with an auditable transition table.
- Checkpoints with content-digest integrity, and durable recovery that performs no
  external provider or governance call.
- Observability: deterministic, replayable event stream and neutral event types.
- Compatibility aliases (`ugence_agent_runtime.compat`) — *reframed in 0.1.1 as honest
  migration guidance, not identity-preserving aliases.*
- Package-local test suite, isolated-install verification, and a standalone demo.

### Boundary decisions
- The core imports **no** concrete governance (TAP, Decision Authority, ActionGate,
  Action Clearance, Code Governance, StoryGraph), **no** robotics, **no** product
  package, and **no** LLM/agent framework.
- Concrete governance and provider adapters remain outside this package (application
  layer or optional integration packages).

### Not included (by design)
- H22 multi-workflow orchestration, distributed scheduling, agent planning/memory,
  LLM routing, new provider kinds, enforcement, external database, GitHub execution.
