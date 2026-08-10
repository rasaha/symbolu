# Agent Runtime — Canonical Execution State

> **Maturity:** `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` — consistent with the rest of
> the package. Additive, offline-verified by the package test suite. Not live-verified,
> pilot-validated, enforcement-ready, or production-validated. No claim here is backed by
> production telemetry.

## Purpose

The Agent Runtime is the **canonical owner of execution-trajectory identity**. For a
single workflow/task it maintains one deterministic, versioned, integrity-protected
representation of *what exact execution trajectory is being coordinated, what caused it,
what immutable action identity is involved, and what external authority/artifact
references are associated with it*.

    Agents may have independent reasoning contexts, but consequential execution must have
    one canonical authoritative execution state.

`CanonicalExecutionState` is that object: a frozen, stdlib-only dataclass with a stable
canonical serialization and a SHA-256 `state_digest`. Semantically equivalent
construction yields an identical digest; changing any identity-bearing field changes it.
It is derived by the runtime from runtime-owned inputs, snapshotted at each meaningful
trajectory point, persisted into checkpoints, and referenced by digest from events.

## Explicit non-goals

`CanonicalExecutionState` is **not**, and must never become:

- shared LLM / agent reasoning context — no prompts, message history, scratchpad, or
  model state;
- agent memory or shared semantic memory;
- RAG context or retrieved documents;
- policy, permission, authorization, clearance, or admitted evidence — it carries
  immutable *references* to such external authority objects, never their substance, and
  constructing one creates no authority;
- an agent selector or model selector — agent/plan references are lineage constraints
  only; carrying one never makes the runtime choose, re-rank, or invent an agent or model;
- the H22 portfolio scheduler / resource ledger / fairness / budget / priority state;
- Runtime Assurance itself (it provides anchors a future assurance consumer can verify,
  but performs no verification or reconciliation);
- a second, independently canonicalized copy of the proposed action payload — action
  identity stays owned by `TransitionProposal` and is referenced here by fingerprint.

It does not solve all multi-agent context-loss problems. It gives many agents and future
governance/assurance modules **one authoritative execution trajectory to reference**; it
does not merge their reasoning, memory, or knowledge.

## Ownership boundary (three separate contexts)

```
Agent Framework(s)          owns  →  Agent Reasoning Context
                                     (prompts, history, RAG, scratchpad, model state)
Agent Runtime               owns  →  Canonical Execution State   ← THIS OBJECT
                                     (trajectory identity, causation, lineage refs,
                                      action-identity ref, runtime status, integrity)
Governance / Decision
Authority / ActionGate      own   →  Enterprise Authority State
                                     (policy, admitted evidence, binding decisions,
                                      authorizations, clearances, delegated authority)
Provider                    owns  →  Execution
Runtime Assurance (future)  owns  →  Observation / verification of execution & effect
```

The runtime **coordinates**. Governance **decides permission**. Providers **execute**.
The Agent Runtime may carry immutable *references* to authority and artifact objects but
never becomes their semantic owner.

- **A. Agent Reasoning Context — OUTSIDE the runtime.** Prompts, message history, RAG
  documents, scratchpad, model state, agent-local memory. Agent frameworks own these.
- **B. Canonical Execution State — the runtime OWNS this.** Workflow/task identity,
  causation, execution lineage, assignment references, immutable action identity,
  external authority references, artifact lineage references, current runtime status,
  integrity digest.
- **C. Enterprise Authority State — EXTERNAL.** Policies, admitted evidence, binding
  decisions, authorizations, clearances, delegated authority. The runtime references
  these; it never authors, admits, or mints them.

## Relationship to `TransitionProposal`

Both objects are needed, and they answer different questions:

| | `TransitionProposal` | `CanonicalExecutionState` |
| --- | --- | --- |
| Question | *What exact provider invocation is being proposed?* | *What is the canonical runtime trajectory in which this exact proposal is being attempted?* |
| Scope | One action's identity | The trajectory that action sits in |
| Action payload | Owns it (deeply-frozen canonical `arguments`) | Does **not** copy it — references `proposal_fingerprint` |

`CanonicalExecutionState` **contains a reference to** `proposal.fingerprint` (plus
descriptive echoes: `provider_id`, `operation`, `idempotency_key`, `proposal_version`),
but it never re-canonicalizes the proposal's arguments. There are never two independently
canonicalized copies of the same action payload; the proposal remains canonical for exact
action identity. The runtime's exact-action invariant is untouched:

    evaluated proposal  ==  actual provider invocation

Canonical execution state records and anchors that trajectory; it neither weakens nor
replaces the proposal.

## Multi-agent motivation

Multiple agents do not need to share one mind. They need to share one **authoritative
execution trajectory**. When several agents (or several reasoning passes of one agent)
contribute to a workflow, their private contexts may diverge — but the runtime keeps a
single, integrity-protected record of which trajectory is real, what caused each
transition, which exact action was proposed, and which external decisions/authorizations
were referenced. A future multi-workflow orchestrator (H22) *composes* per-execution
canonical states; it does not turn the runtime into a portfolio scheduler. A future
Runtime Assurance consumer *verifies against* these anchors; it does not live here.

## Schema (v1) and field classification

`state_version = "1"`. Every field is a flat scalar (`str`/`int`/`float`/`None`) or an
ordered tuple of strings — never a nested arbitrary structure — so canonical
serialization is a single `json.dumps(..., sort_keys=True)`. Each field is classified as
**derived** (produced from runtime-owned state), **referenced** (copied verbatim from an
external object governance/lineage supplied), or **deferred** (no canonical upstream
source in the reference engine yet — optional, defaults to unavailable, never fabricated).

| Group | Field | Classification | Source |
| --- | --- | --- | --- |
| Identity | `state_version` | derived | constant `"1"` |
| | `runtime_id`, `runtime_version` | derived | `AgentRuntimeConfig` |
| | `workflow_id`, `instance_id` | derived | `WorkflowInstance` |
| | `task_id` | derived | `TaskInstance` |
| Correlation / causation | `correlation_id` | derived | `WorkflowInstance.correlation_id` |
| | `causation_id`, `parent_workflow_ref`, `parent_task_ref` | referenced | `ExecutionLineage` seam (workflow and/or task level) |
| Agent / plan lineage | `assigned_agent_ref`, `agent_team_plan_ref`, `assignment_digest`, `authority_scope_ref` | referenced | `ExecutionLineage` seam (workflow and/or task level; AWC/H16 constraints only) |
| Runtime state | `workflow_status`, `task_status`, `attempt` | derived | instance / task |
| Action identity | `provider_id`, `operation`, `idempotency_key`, `proposal_version` | derived | `TransitionProposal` (descriptive echo) |
| | `proposal_fingerprint` | referenced | `TransitionProposal.fingerprint` (the single action identity) |
| Authority lineage | `governance_disposition` | referenced | `GovernanceEvaluation.disposition` |
| | `evaluation_reference`, `authorization_reference`, `clearance_reference`, `valid_until` | referenced | `GovernanceEvaluation` (verbatim; `None` when governance produced none) |
| Data / artifact lineage | `input_artifact_refs`, `output_artifact_refs`, `evidence_refs` | referenced | `ExecutionLineage` seam (workflow and/or task level) |
| Execution lineage | `execution_reference`, `result_digest` | deferred | future Runtime Assurance / receipt consumer — currently always `None` |
| Integrity | `state_digest` | derived | SHA-256 over all fields **except** itself |

**Deliberately excluded** from v1 (documented rather than faked):

- `decision_reference` — the reference engine's `GovernanceEvaluation` exposes
  `evaluation_reference` / `authorization_reference` / `clearance_reference`; there is no
  distinct, canonical "decision reference" source to populate honestly.
- `attempted_action_digest` — would duplicate `proposal_fingerprint`. The proposal
  fingerprint *is* the attempted action digest; a second field would invite a second,
  divergent action identity.

## Lineage is two-level (workflow-common + per-task)

The motivating case is multiple agents in one workflow:

```
Workflow
 ├─ Task 1 → Research Agent
 ├─ Task 2 → Risk Agent
 └─ Task 3 → Execution Agent
```

So lineage is supplied at two levels and combined per task via `ExecutionLineage.overlay`
(task fields win when set; a sequence field wins when non-empty):

- **Workflow-common** — `start_workflow(definition, lineage=…)`, stored on
  `WorkflowInstance.lineage`. Natural home for `agent_team_plan_ref`, `parent_workflow_ref`.
- **Per-task** — `start_workflow(definition, task_lineage={task_id: …})`, stored on
  `TaskInstance.lineage`. Natural home for `assigned_agent_ref`, `causation_id`, input/
  output artifacts, evidence.

Each task's canonical state is therefore attributed to *its own* agent, artifacts, and
causation, while still inheriting workflow-common references. A per-task lineage that sets
only `assigned_agent_ref` still inherits the workflow's team plan.

## Lifecycle: immutable snapshots, not a mutable blob

Rather than one mutable state object, the runtime records a fresh immutable snapshot at
each meaningful transition, so historical audit reconstruction is never ambiguous:

```
S0  task ready / proposal constructed          (task READY, proposal, pre-governance)
 ↓
S1  governance disposition returned            (+ disposition & references, if any)
 ↓
S2  clearance validated / provider invoking    (task RUNNING)
 ↓
S3  provider completed                          (attempt count reflects outcome)
 ↓
S4  task completed / failed                     (terminal task status)
```

Each snapshot has a deterministic `state_digest`. `runtime.execution_state(instance_id,
task_id)` returns the latest snapshot for a task; `task_id=None` derives a workflow-level
snapshot on demand. Every snapshot — not only the latest per task — is also retained in a
per-instance **journal** keyed by digest, so a digest anchored on any earlier event stays
resolvable via `runtime.execution_state_by_digest(instance_id, state_digest)`. There is
**no** API to overwrite a snapshot — execution truth is runtime-owned and read-only.

## Integrity, events, checkpoints, recovery

- **Digest.** `compute_digest()` hashes the canonical payload (which excludes
  `state_digest`). `sealed()` returns a copy with the digest attached; `is_intact()`
  re-verifies. Unsupported identity-bearing types fail closed with `ExecutionStateError`.
- **Events.** `execution_state_digest=<digest>` is attached to `TASK_READY`,
  `GOVERNANCE_EVALUATION_REQUESTED`, `GOVERNANCE_DISPOSITION_RECEIVED`, `TASK_STARTED`,
  `PROVIDER_INVOKED`, `PROVIDER_COMPLETED`, `TASK_COMPLETED`, `TASK_FAILED`. Digest
  references only — the full state never bloats the event stream; sequencing is unchanged.
- **Checkpoints — two integrity boundaries.** `Checkpoint` gains `checkpoint_version`
  (`"1"`), a self-verifying per-task `execution_states` section, the digest-keyed
  `execution_state_journal`, and the typed **lineage source** (`workflow_lineage` +
  `task_lineage`) — the latter preserved *separately* from historical snapshots so future
  snapshots after recovery keep the same references, including for tasks that had not yet
  run. Two independent digests protect it:
  - `digest` — the **base coordination digest**, computed over exactly the original payload.
    Unchanged, so **pre-existing checkpoints verify byte-identically**.
  - `extension_digest` — a **separate v1 boundary** over the entire canonical-state
    extension (`checkpoint_version` + `execution_states` + `execution_state_journal` +
    `workflow_lineage` + `task_lineage`). The base digest deliberately does *not* cover the
    extension, so `extension_digest` is what protects the **lineage source** and the
    **collection membership** — closing the gap where the lineage source rode along
    unprotected by either the base digest or the per-snapshot digests. A legacy (`"0"`)
    checkpoint carries no extension and no `extension_digest`.
- **Cross-binding & consistency.** `validate_execution_states()` enforces — beyond each
  snapshot's own digest — that the map key equals the snapshot's own key field; that
  instance / workflow / correlation identity match the checkpoint; that the referenced task
  exists; that the schema version is supported; that **every latest snapshot is resolvable
  in the journal by its own digest and is the same snapshot** (the public "every digest
  resolvable" guarantee); and that the **lineage source is structural** (keys reference
  known tasks, values deserialize). `runtime_id`/`runtime_version` are deliberately **not**
  bound to the writer — they are *origin* provenance (the runtime that created that
  historical snapshot), so a checkpoint written after a recovery across a runtime upgrade
  legitimately carries a **mixed-version journal** and still recovers. An inconsistent
  canonical state fails closed with a precise reason — never silently accepted *or*
  silently discarded.
- **Self-recoverability.** The engine validates every checkpoint (base digest + extension
  digest + binding) *before* persisting it, so the runtime never emits a checkpoint its own
  recovery validator would reject — every checkpoint it writes is self-recoverable under its
  declared schema (subject to later corruption).
- **Recovery — versioned gate.** Recovery first rejects an **unknown `checkpoint_version`**
  (fail closed rather than interpret a future schema under today's rules). For `"1"` it
  requires the base digest valid, the **extension digest valid**, and cross-binding valid;
  for `"0"` (legacy) it requires the base digest valid and no extension data present. It
  then restores the lineage source, the per-task latest snapshots, and the journal; and
  **never fabricates** a missing decision reference, authorization, clearance, proposal
  fingerprint, execution reference, or agent provenance. Recovery still performs no provider
  or governance call, and recovered non-terminal work still requires explicit continuation
  (a fresh governance evaluation), so a stored `valid_until` is never consumed as a live
  grant.

> **Threat-model note.** These digests protect against corruption, partial writes, and any
> intermediary that tampers without recomputing the digest — bringing the lineage source to
> parity with the base coordination data. They are *not* signatures: an actor with full
> write access to the checkpoint store who recomputes a digest is out of scope (that
> requires keyed signing, which this neutral, stdlib-only package deliberately does not
> embed). The structural and latest↔journal consistency checks still catch a class of
> re-sealed tampering (e.g. omitting a journal entry a latest snapshot points to).

## What is enforced mechanically

- Deterministic digest excluding `state_digest`; identity-bearing change ⇒ digest change;
  semantic equality ⇒ digest equality (tests: determinism, sensitivity).
- Canonical state references exactly one action identity — the active proposal
  fingerprint — and carries no `arguments` field (test: no-action-duplication).
- Governance disposition and references are recorded verbatim; missing references stay
  `None` (tests: governance-lineage fidelity, missing-references).
- Supplied lists/dicts are frozen at construction; later external mutation cannot alter
  identity (tests: immutability).
- Agent/plan references are carried but never drive selection (test: agent-lineage
  neutrality).
- Constructing a state creates no authority and cannot turn HOLD/BLOCK/ESCALATE into
  CLEAR; there is no mutation API (tests: authority boundary).
- Per-task lineage overlays workflow-common lineage, so sibling tasks are attributed to
  their own agent/artifacts (test: task-specific lineage).
- Lineage continuity survives recovery — a snapshot built after recovery keeps the same
  references (test: recovery lineage continuity).
- Checkpoint round trip preserves intact lineage; legacy checkpoints remain supported;
  historical digests stay resolvable after recovery; cross-binding rejects a relabelled or
  foreign-instance snapshot and an unsupported version with a precise reason; tampering
  fails closed; recovery has no side effects (tests: checkpoint/recovery/cross-binding).
- The `extension_digest` covers the lineage source and snapshot-collection membership, so
  tampering the persisted lineage fails recovery even though the base digest and the
  per-snapshot digests still pass (test: lineage-source tampering); an unknown
  `checkpoint_version` fails closed; omitting a journal entry a latest snapshot points to is
  caught even when the extension digest is re-sealed; a lineage entry for an unknown task
  fails closed (tests: checkpoint integrity boundary).
- A snapshot's `runtime_id`/`runtime_version` are origin provenance, not bound to the
  checkpoint writer, so a mixed-version journal produced by recovery across a runtime upgrade
  still recovers; every checkpoint the engine emits validates before it is persisted
  (tests: runtime-upgrade recovery, self-recoverability).
- Unsupported `state_version` and non-finite `valid_until` fail closed (tests: hardening).

## Current limitations / remaining gaps

- **Single workflow.** No multi-workflow / portfolio composition (that is H22, and is
  deliberately out of scope).
- **No durable production persistence.** The in-memory stores are for tests/simulation.
- **No AWC adapter.** `ExecutionLineage` is a neutral seam; there is no implemented
  upstream planner adapter, so agent/plan references are supplied by the caller or absent.
- **No Runtime Assurance consumer.** `execution_reference` / `result_digest` are deferred
  seams with no upstream source yet.
- **Cross-workflow causation** is representable as references but has no runtime producer.
- **Not production-validated.** See the maturity banner above.
