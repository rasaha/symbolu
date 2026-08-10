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
| | `causation_id`, `parent_workflow_ref`, `parent_task_ref` | referenced | `ExecutionLineage` seam (optional) |
| Agent / plan lineage | `assigned_agent_ref`, `agent_team_plan_ref`, `assignment_digest`, `authority_scope_ref` | referenced | `ExecutionLineage` seam (optional; AWC/H16 constraints only) |
| Runtime state | `workflow_status`, `task_status`, `attempt` | derived | instance / task |
| Action identity | `provider_id`, `operation`, `idempotency_key`, `proposal_version` | derived | `TransitionProposal` (descriptive echo) |
| | `proposal_fingerprint` | referenced | `TransitionProposal.fingerprint` (the single action identity) |
| Authority lineage | `governance_disposition` | referenced | `GovernanceEvaluation.disposition` |
| | `evaluation_reference`, `authorization_reference`, `clearance_reference`, `valid_until` | referenced | `GovernanceEvaluation` (verbatim; `None` when governance produced none) |
| Data / artifact lineage | `input_artifact_refs`, `output_artifact_refs`, `evidence_refs` | referenced | `ExecutionLineage` seam (optional) |
| Execution lineage | `execution_reference`, `result_digest` | deferred | future Runtime Assurance / receipt consumer — currently always `None` |
| Integrity | `state_digest` | derived | SHA-256 over all fields **except** itself |

**Deliberately excluded** from v1 (documented rather than faked):

- `decision_reference` — the reference engine's `GovernanceEvaluation` exposes
  `evaluation_reference` / `authorization_reference` / `clearance_reference`; there is no
  distinct, canonical "decision reference" source to populate honestly.
- `attempted_action_digest` — would duplicate `proposal_fingerprint`. The proposal
  fingerprint *is* the attempted action digest; a second field would invite a second,
  divergent action identity.

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
snapshot on demand. There is **no** API to overwrite a snapshot — execution truth is
runtime-owned and read-only to callers.

## Integrity, events, checkpoints, recovery

- **Digest.** `compute_digest()` hashes the canonical payload (which excludes
  `state_digest`). `sealed()` returns a copy with the digest attached; `is_intact()`
  re-verifies. Unsupported identity-bearing types fail closed with `ExecutionStateError`.
- **Events.** `execution_state_digest=<digest>` is attached to `TASK_READY`,
  `GOVERNANCE_EVALUATION_REQUESTED`, `GOVERNANCE_DISPOSITION_RECEIVED`, `TASK_STARTED`,
  `PROVIDER_INVOKED`, `PROVIDER_COMPLETED`, `TASK_COMPLETED`, `TASK_FAILED`. Digest
  references only — the full state never bloats the event stream; sequencing is unchanged.
- **Checkpoints.** `Checkpoint` gains `checkpoint_version` (`"1"`) and a self-verifying
  `execution_states` section. The base coordination `digest` is computed over exactly the
  original payload, so **pre-existing checkpoints verify byte-identically** and their
  digest semantics are unchanged. A checkpoint deserialized without a version tag is
  treated as legacy `"0"` with execution-state lineage unavailable.
- **Recovery.** Restores established lineage verbatim, fails closed on tampering
  (`verify_execution_states`), and **never fabricates** a missing decision reference,
  authorization, clearance, proposal fingerprint, execution reference, or agent
  provenance. Recovery still performs no provider or governance call.

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
- Checkpoint round trip preserves intact lineage; legacy checkpoints remain supported;
  tampering fails closed; recovery has no side effects (tests: checkpoint/recovery).

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
