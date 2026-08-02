# Workflow-Service Ownership — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4A, §9.1).
> Verified against live code at commit `3ec11e4e`.

## 1. What already exists that might provide workflow capability

| Capability the Workflow Service needs | Exists as code? | Where / verdict |
|---|---|---|
| durable workflow state | **No** | `agent_runtime_v2/` is **docs-only**; `agent_runtime_migration` `RuntimeState` is an in-memory dataclass, not persisted |
| event handling | Partial | `agent_runtime_migration` tracing; `control_plane` single-request routing (mock adapters) |
| retries | Yes (in-memory) | `agent_runtime_migration/runtime/retry.py` `RetryPolicy`; DA `RetryClassification` |
| pause/resume | **No** | only a terminal `AWAITING_HUMAN` status; no resume-from-store |
| idempotency | Partial | DA `idempotency_key`/`execution_idempotency_key`; StoryGraph ledger dedup |
| stage orchestration | Partial | `control_plane/orchestrator.py` routes one request synchronously; no persisted workflow |
| state transitions | Yes (in-object) | DA `DecisionCase` static transition table (`decisions/lifecycle.py:17`); provider lifecycle table |
| event sourcing | **No** | not implemented anywhere as code |
| audit references | Partial→Yes | DA `AuditEvent`; StoryGraph `durable_audit` (SQLite, hash-chained); `agentic/ledger` |
| reconciliation | Yes | DA `services/reconciliation_service.py` |
| tenant isolation | Partial | `tenant_id` on DA records; StoryGraph provider registry isolates tenants; **not** in GPF resolution |
| human tasks | **No** (durable) | only `AWAITING_HUMAN` status |
| webhook processing | **No** | none in any workflow component |

## 2. Decision Case lifecycle ≠ Code Governance workflow

Decision Authority's `DecisionCase` state machine (`CaseStatus`: CREATED → … → DECIDED →
{SUPERSEDED, CLOSED}; terminal {SUPERSEDED, CANCELLED, CLOSED}; **no executed state**) governs the
lifecycle of a *decision case*, over **in-memory repository ports** (no durable DB shipped). It is
**not** the Code Governance merge workflow and must not be overloaded to become one. The Code
Governance workflow spans ingestion → evidence → decision → authorization → clearance → execution →
reconciliation, which is broader than a single decision case.

## 3. Ownership matrix — Code Governance Workflow Service

**Owns (product-internal, no authority):**
- product workflow state and its state machine (see `STATE_MACHINE.md`);
- event correlation and reference propagation between stages;
- stage invocation and ordering;
- GitHub webhook handling;
- pause/resume and timeout handling;
- GitHub reconciliation (branch/PR/check state);
- user-facing workflow status;
- **fail-closed enforcement of the governance chain (§4.7)** — the one behavior it must guarantee.

**Must NOT own:** evidence judgment (TAP) · binding approval authority (Decision Authority) ·
ActionGate authorization · ACP clearance judgment · StoryGraph risk judgment · patch-selection
authority (adjudicator) · merge permission independent of the authority chain.

## 4. Correct implementation choice

> Do **not** place Code Governance inside another authority merely because it has a workflow engine.

Given that **no durable workflow engine exists as code** (agent_runtime_v2 is docs; agent_runtime_migration
is in-memory; control_plane is single-request/mock), the recommended shape is:

**Option 1 — a new product package (`products/code-governance/workflow/`) that owns its own durable
state machine and persistence, reusing existing primitives** (DA records/reconciliation, StoryGraph
`durable_audit` for the tamper-evident trail, GPF `fingerprint`, the resolution/lifecycle patterns).

Rejected alternatives:
- **A thin module over an existing durable engine** — there is no such engine to be thin over.
- **Extending Decision Authority / control_plane** — would fold coordination into an authority /
  a different stack and violate §4A.

The Workflow Service is the analogue of the platform's *Optional Orchestrator*: it composes, it does
not acquire authority from what it invokes.

## 5. Candidate-generation orchestration (§9.1)

Candidate generation is **deliberately not owned by any governance component** and **not** by the
Workflow Service. In MVP 1 there is **no generation orchestration**: a human or a single external
agent produces one PR and Ugence governs it. Future owners (Agent Runtime / optional orchestrator /
dedicated competitive-development service) are left open and are out of scope for this audit.

## 6. Dependency the choice creates

Because the Workflow Service must own **durable** state and the durable-audit backend for the
decision kernel is **PARTIAL** (see `DURABLE_AUDIT_AND_RECONSTRUCTION.md`), workflow durability is a
**pilot/production prerequisite** (P0/P1), not available out-of-the-box. Phase A can build the
state machine in-process; enforced modes (1C) require durable persistence.
