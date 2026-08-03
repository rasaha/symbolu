# ADR — Agent Workforce Composer ↔ H16 Canonicalization and Downstream Boundaries

**Status:** Accepted (Phase 0, documentation & contract-freeze only)
**Date:** 2026-08-03
**Owners:** Ugence platform architecture
**Related:**
- [`ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`](../../ADR_MODEL_SELECTION_POLICY_PLACEMENT.md) — placement pattern this ADR mirrors
- [`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md)
- The seven `AGENT_WORKFORCE_COMPOSER_*.md` documents (PR #1305, merge `0fa80fe4…`)
- The Policy Workflow Compiler (`packages/tooling/policy-workflow-compiler/`, PR #1303, merge `96afb58a…`)
- Audit set: [`docs/audits/agent_workforce_composer_phase0/`](../audits/agent_workforce_composer_phase0/)

> *This ADR changes **no** production code, package, wheel, public API, schema, frozen
> identifier, serialization, digest, or authority boundary. It corrects documentation,
> freezes contracts, and assigns canonical ownership. Every implied code/package change
> is explicitly deferred to later, compatibility-controlled phases. The platform-freeze
> substantive digest is unchanged before and after this phase
> (`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).*

---

## Central decision

> **Option A — Canonicalize deterministic agent-selection concepts into the Agent
> Workforce Composer (AWC).** AWC becomes the canonical, offline, deterministic
> *planning* capability that turns a compiled `WorkflowIR` into an explainable,
> permission-bounded `AgentTeamPlan`. The H16 coordination layer
> (`agentic/agentic_framework/`) **retains all runtime coordination** — delegation,
> dispatch, supervision, recovery, live availability, and (where explicitly enabled)
> LLM-based routing. H16 eventually **consumes** AWC's `AgentTeamPlan` through a
> narrowing-only adapter; duplicated selection concepts are canonicalized into AWC and
> re-exported from H16 only where semantics are byte-identical.

This is a decision to prevent the most expensive architectural mistake in this roadmap:
building a second agent-selection system while H16 already contains overlapping
selection concepts.

---

## Context

Two facts, both verified against the live default branch
(`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` @ `0d8c4e05`):

1. **The Policy Workflow Compiler is implemented** (PR #1303). It is the independently
   packaged `ugence-policy-workflow-compiler` distribution (namespace
   `ugence_policy_workflow_compiler`, surface `…​.api`, 71 public names). It emits a
   typed, deterministic `WorkflowIR` (`workflow_ir.v1`: 14 node kinds, 9 edge kinds,
   content-addressed node ids), a capability manifest, assurance artifacts, and a
   content-addressed compiled package. Document extraction, NLP interpretation, and
   runtime deployment remain outside its implemented Phase 1 scope. The merged AWC
   documents describe it as "spec-only" / "not yet implemented" / "when it ships" —
   this is stale and is corrected in the same PR as this ADR (see
   `STALE_ASSUMPTION_INVENTORY.md`).

2. **H16 already contains selection concepts** (`agentic/agentic_framework/coordination.py`,
   `multi_agent.py`). `AgentProfile`, `CapabilityRegistry.candidates_for`,
   `CoordinationGoal`, `DelegationContract`, and the deterministic hard-constraint checks
   in `AuthorityModel` overlap materially with what AWC proposes to own. These names
   also **collide** with distinct AWC-proposed and compiler types. `AuthorityModel` is
   the sole authority decision-maker; `multi_agent.py` has no authority model and hosts
   the nondeterministic `LLMRouter`. Full inventory: `H16_OVERLAP_INVENTORY.md`.

The question is whether the deterministic selection concepts should be **canonicalized
into AWC** (Option A), factored into a **shared neutral contract** consumed by both
(Option B), or left **canonical in H16** with AWC as an adapter over it (Option C).

---

## Options considered

### Option A — Canonicalize deterministic selection into AWC *(SELECTED)*

**AWC owns** (offline, pure, snapshot-pinned, deterministic, explainable):
immutable agent capability profiles used for selection; frozen registry snapshots;
workflow-role requirements; hard-constraint eligibility results; elimination reasons;
deterministic scoring; team composition and alternatives; proposed permission bounds;
selection explanations; immutable team plans; fallback plans; replay records.

**H16 retains** (runtime, stateful, availability-aware): runtime coordination; task
delegation; dispatch; execution supervision; runtime recovery; live availability
handling; runtime fallback; LLM-based routing where explicitly enabled; all side
effects. H16 eventually consumes AWC artifacts (or uses compatibility adapters).

*Pros.* Correct dependency direction (leaf AWC ← compiler data; H16 → AWC). Preserves
AWC's offline determinism and independent packaging. Single canonical home for
selection. Isolates nondeterministic runtime (`LLMRouter`) from deterministic planning.
Mirrors the accepted Model Selection placement pattern (canonical capability, data-only
seams).

*Cons.* Requires a compatibility layer for existing H16 consumers (8 modules + package
re-export + tests). Name collisions must be resolved by namespacing, not merging.

### Option B — Shared neutral contract package

A shared package owns the common profile/registry/assignment contracts; AWC and H16
both depend on it.

*Rejected because* it adds an abstraction layer with no third consumer, weakens
ownership clarity (two owners for one concept), and still leaves the selection *logic*
(eligibility, scoring, composition) unhomed — the contract types are the easy part; the
deterministic selection procedure is the substance, and it belongs in one capability.
A neutral contract is warranted only for the two genuine boundary fields
(`assigned_agent`, `authority_scope`), which already exist as plain fields on H22's
`PortfolioWorkflowEntry` and need no new package.

### Option C — Keep H16 canonical; AWC adapts over H16

AWC becomes an adapter over H16 selection objects.

*Rejected because* it inverts the dependency direction: AWC (a would-be leaf) would
import into the coupled `agentic/` runtime tree, pulling in live coordination, shared
budget/memory, and the nondeterministic `LLMRouter`. That destroys AWC's offline
determinism, independent packaging, and replayability, and violates the repo's
leaf-capability / dependency-direction rules (`DEPENDENCY_DIRECTION.md`). It also keeps
selection welded to runtime, which is exactly the conflation this reconciliation exists
to undo.

**Decision: Option A**, supported by the live audit (dependency direction, determinism,
packaging independence, and the concrete H16 overlap all point the same way).

---

## Canonical ownership matrix

| Concern | Canonical owner |
|---|---|
| Workflow and governance interpretation | Policy Workflow Compiler |
| Workflow-role extraction | Agent Workforce Composer |
| Frozen agent registry snapshot | Agent Workforce Composer *(pending confirmation of an upstream registry-of-record; if one is later declared, AWC pins its snapshot rather than authoring it — see Open questions)* |
| Agent eligibility | Agent Workforce Composer |
| Agent ranking | Agent Workforce Composer |
| Team composition | Agent Workforce Composer |
| Proposed permission bounds | Agent Workforce Composer |
| Binding permission enforcement | Agent Runtime / ActionGate / Action Clearance |
| Runtime task delegation | H16 coordination (→ Agent Runtime) |
| Runtime dispatch | Agent Runtime |
| Runtime recovery | H16 / Agent Runtime |
| Model choice | Model Selection |
| Multi-workflow scheduling | H22 |
| Binding business decision | Decision Authority |
| Exact-action authorization | ActionGate |
| Operational clearance | Action Clearance |
| Sequence-risk advisory analysis | StoryGraph |

Every selection, runtime, scheduling, model, and authority responsibility has exactly
one owner. Uncertain ownership is flagged explicitly (registry-of-record, above).

---

## Frozen boundaries

### AWC ↔ Policy Workflow Compiler
AWC consumes the canonical `WorkflowIR` (`workflow_ir.v1`) via a pure, versioned,
data-only adapter (`CompilerWorkflowAdapter`, specified in
`POLICY_COMPILER_CONTRACT_AUDIT.md`, **not** implemented in Phase 0). The adapter
classifies each `WorkflowNode` into one of seven dispositions
(`AI_AGENT_ELIGIBLE`, `NO_AI_AGENT_REQUIRED`, `DETERMINISTIC_SERVICE_PREFERRED`,
`HUMAN_AUTHORITY_REQUIRED`, `HUMAN_REVIEW_REQUIRED`,
`EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`, `UNSUPPORTED_NODE`), fails closed on unknown
versions/nodes, preserves capability ownership and provenance, and **never** reclassifies
an `AUTHORITATIVE` governance node (Decision Authority / ActionGate / Action Clearance)
as agent work.

### AWC ↔ H16
```
AWC:  offline · pure · snapshot-pinned · deterministic · explainable · plan-producing · side-effect free
H16:  runtime · stateful · availability-aware · dispatching · recovering · supervising · potentially nondeterministic where explicitly configured
```
AWC output: **`AgentTeamPlan`**. H16 input adapter: `AgentTeamPlan → runtime delegation
and coordination state`. H16 **must not** silently reselect a different agent in any way
that broadens permissions, authority scope, provider allowance, data residency, tool
access, cost ceiling, or quality floor. Runtime fallback is chosen from an AWC-approved
fallback set or triggers governed reassessment.

### AWC ↔ Model Selection
AWC selects **functional AI agents** for workflow roles; Model Selection selects the
**models/providers** that may power a selected agent invocation. AWC may emit
`model_policy_ref` / `model_requirement_ref` / `model_constraint_ref`. AWC must not rank
LLMs, call provider registries, choose endpoints, implement fallback models, or
duplicate Model Selection policy. Model Selection must not decide which functional agent
owns a role.

### AWC ↔ Agent Runtime
Future neutral handoff: `AgentTeamPlan → Agent Runtime adapter →
WorkflowDefinition / TaskDefinition / runtime assignment objects`. AWC fields are
planning metadata; some become runtime constraints; the runtime may **narrow** but
**never broaden** authority/permission bounds; unsupported agent versions fail closed;
availability changes are handled by the runtime/H16 within the plan's approved fallback
set; assignment digests and policy versions are preserved; execution outcomes refer back
to the originating plan. Adapter **not** implemented in Phase 0.

### AWC ↔ H22
AWC **produces** staffing/assignment artifacts (`assigned_agent` + `authority_scope`
per role, verified as `PortfolioWorkflowEntry` fields at
`multi_workflow_orchestration.py:855-856`); H22 **schedules** already-staffed workflows.
H22 must not select agents, change assignments, broaden authority, invent fallbacks, or
override residency/provider constraints. On unavailability H22 may pause or surface — it
must not perform ungoverned reselection.

### Authority boundary (binding authority stays out of AWC)
AWC proposes permission **bounds** only. Binding business decisions (Decision
Authority), exact-action authorization (ActionGate), and operational clearance (Action
Clearance) remain outside AWC. StoryGraph remains the advisory sequence-risk analyzer.

---

## Compatibility strategy (specified, not executed)

Per `COMPATIBILITY_RISK.md`, three treatments are distinguished:

1. **Identity-preserving** re-export — only where semantics are byte-identical.
   Candidate: `AgentProfile`, iff its fields/frozen semantics are unchanged, guarded by
   a serialization round-trip test.
2. **Adapter-based** — where runtime/mutable behavior differs: `CapabilityRegistry`
   (mutable availability vs. immutable snapshot), `DelegationContract` (runtime grant vs.
   planning `AgentAssignment`), `AuthorityModel` (runtime `authorize()` vs. pure
   eligibility). Adapters are **narrowing-only**.
3. **Retained H16 runtime objects** — `Coordinator`, mutable `AgentAssignment`,
   ledgers, traces, all workers, and the whole `multi_agent.py` layer including
   `LLMRouter`. Not migrated.

Import-path preservation, object-identity expectations, serialization/behavioral
compatibility, deprecation policy, migration order, rollback, test strategy, and likely
SemVer classification are recorded in `COMPATIBILITY_RISK.md`. Name collisions
(`AgentProfile`, `CapabilityRegistry`, `AgentAssignment`) are resolved by **distinct
namespaces**, never by merging semantically different types.

---

## Consequences

- The seven AWC documents are corrected to describe the compiler as implemented and to
  consume the canonical `WorkflowIR`; the former "spec-only upstream" risk is replaced by
  **`UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`**.
- AWC's frozen target location is `packages/capabilities/agent-workforce-composer/`
  (distribution `ugence-agent-workforce-composer`, namespace `ugence_agent_workforce_composer`;
  leaf, stdlib-only + governance-contracts + compiler data contract). Not created here.
- No H16, compiler, Model Selection, Agent Runtime, H22, Decision Authority, ActionGate,
  Action Clearance, or StoryGraph behavior changes in Phase 0.
- P1 implementation **must not start** until the exit gates below pass.

## Exit gates (P1 may not begin until all pass)

1. This ADR accepted; exactly one option selected with rationale. ✔ (Option A)
2. Every relevant H16 symbol has a disposition (`H16_OVERLAP_INVENTORY.json`). ✔
3. The live `WorkflowIR` contract and the `CompilerWorkflowAdapter` seam are documented
   (`POLICY_COMPILER_CONTRACT_AUDIT.md`). ✔
4. Ownership matrix frozen (above); no concern has two owners. ✔
5. All five boundaries frozen (above) and reflected in
   `docs/architecture/agent_workforce_composer_boundaries.json`. ✔
6. All seven AWC documents agree with this ADR and contain no stale "spec-only" /
   "when it ships" compiler language (validated by the doc-consistency script/CI). ✔
7. Platform-freeze substantive digest unchanged; no production package added; H16 and
   compiler source behavior unmodified. ✔

## Open questions (unresolved, do not block Phase 0)

- **Registry-of-record.** Whether the frozen agent registry snapshot is authored by AWC
  or pinned from a declared upstream registry owner (e.g. AI Hiring). AWC pins whatever
  is canonical; if an upstream owner is later declared, ownership of *authoring* the
  registry moves there while AWC keeps ownership of the *snapshot pinning*.
- **`AgentProfile` field identity.** Whether the canonical AWC profile can be a
  byte-identical re-export for H16 or must be an adapter (decided by a P1 field-diff test).
- **Demand validation.** No repository evidence of customer pull for AWC; remains
  `[UNVALIDATED]`. This ADR resolves architecture, not demand.
