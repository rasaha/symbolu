# Agent Workforce Composer — Architecture

**Status:** `[SPEC]` design / pre-implementation. Companion to `AGENT_WORKFORCE_COMPOSER_DESIGN_SPEC.md`.
Claim labels: `[EXISTING] [SPEC] [INFERENCE] [PROPOSED] [DEFERRED] [UNVALIDATED]` (see design spec §1).

---

## 1. Architectural stance

`[SPEC]` AWC is a **leaf capability shaped as a pure decision function** over frozen inputs, modeled directly on the
existing Model Selection Policy Engine (`[EXISTING]` `packages/capabilities/model-selection`). It has three defining
properties, each inherited from a verified repository pattern:

1. **Constraint-first, fail-closed, two-stage selection** — eligibility gate (never ranks) → policy scorer (only
   over eligible). Source pattern: `ExecutionGate` → `ModelPolicy` (`ugence_model_selection`), lifted one level up
   from *models* to *agents-for-roles* and extended with a *team-composition* stage.
2. **Policy is data; the engine is a generic interpreter** — `CompositionPolicy` is a versioned declarative
   artifact; the code is a deterministic interpreter (`[EXISTING]` Model Selection §2.1).
3. **Leaf dependency posture** — stdlib + at most `ugence-governance-contracts` and domain-neutral
   `ugence-decision-authority` primitives; all upstream inputs are **injected data**, never imports (`[EXISTING]`
   the acyclic, machine-verified boundary rule in `UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md`).

`[SPEC]` AWC is a **planner, not a runtime**: input is *data describing work and agents*; output is *a plan artifact*.
It never opens a socket, calls a provider, executes an agent, or reads a clock.

---

## 2. Context diagram (where AWC sits)

```
        ┌─────────────────────────────┐
        │  Policy Workflow Compiler   │  [EXISTING: spec-only]
        │  → governed workflow graph  │
        └──────────────┬──────────────┘
                       │  (injected data: WorkflowGraphSource)
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AGENT WORKFORCE COMPOSER  [SPEC]                 │
│  role extraction → eligibility → scoring → team composition →      │
│  permission/authority bounding → fallback → AgentTeamPlan + ledger │
└───────┬───────────────────────────┬──────────────────────┬────────┘
        │ (injected data)           │ (injected data)       │ emits (data)
        ▼                           ▼                        ▼
  AgentRegistrySnapshot     EnterpriseAgentPolicy      AgentTeamPlan
  [EXISTING concepts in       CompositionPolicy         + SelectionExplanation
   H16 coordination.py;                                 + SelectionReplayRecord
   ADAPT/canonicalize]                                        │
                                                              │ optional handoff (as neutral data)
        ┌─────────────────────────────────────────────────────┼───────────────────────────────┐
        ▼                        ▼                     ▼        ▼                 ▼               ▼
   Agent Runtime            H22 scheduler       Model Selection  Decision Authority  ActionGate  Action Clearance
   executes WorkflowDef.    consumes            picks model per  binding decisions   authorizes  clears at commit
   selects providers        assigned_agent +    assigned agent   (no AI actor)       actions     time
   [EXISTING: COMPOSE]      authority_scope      [REFERENCE+     [OUT_OF_SCOPE:      [OUT_OF_    [OUT_OF_SCOPE]
                            [OUT_OF_SCOPE:        COMPOSE]         boundary]           SCOPE]
                             boundary]
```

`[EXISTING]` Every downstream authority is reached by **artifact/data**, not by AWC importing it. This mirrors how
the Agent Runtime reaches governance only through an injected `GovernanceHook` and is *forbidden* by test from
importing Decision Authority / ActionGate / Action Clearance / StoryGraph / Model Selection
(`packages/runtime/agent-runtime/tests/test_import_boundaries.py`).

---

## 3. Internal component decomposition

`[SPEC]` Proposed `src/ugence_agent_workforce_composer/` layout, mirroring the file-role split of
`ugence_model_selection` (`model.py`/`gate.py`/`policy.py`/`registry.py`/`fingerprint.py`/`reason_codes.py`/
`states.py`/`api.py`/`version.py`):

| Module | Role | Source pattern (`[EXISTING]`) |
|---|---|---|
| `models.py` | Frozen dataclasses: `WorkflowRoleRequirement`, `AgentProfile`, `AgentCapability`, `CapabilityEvidence`, `AgentRegistrySnapshot`, `EnterpriseAgentPolicy`, `CompositionPolicy`, `CompositionRequest` | `model.py` (`Request`,`Candidate`,`Signal`,`GateConfig`) |
| `states.py` | Enums + evidence/verdict types: `EligibilityState`, `Verdict`, `Criticality`, `ConditionResult`, `AgentEligibilityResult`, evidence provenance/precedence | `states.py` |
| `reason_codes.py` | `EliminationReason` append-only taxonomy + `normalize_raw` | `reason_codes.py` |
| `extraction.py` | Role extraction: workflow graph → `WorkflowRoleRequirement[]` \| `NonAgentDisposition[]` | (new; adapter over compiler IR) |
| `eligibility.py` | `AgentEligibilityGate` — hard-constraint elimination, never ranks | `gate.py` (`ExecutionGate`) |
| `scoring.py` | `AgentScorer` — deterministic weighted ranking over eligible only | `policy.py` (`ModelPolicy.select`) |
| `composition.py` | `TeamComposer` — interface/SoD/concentration/correlation checks, `TeamCandidate` ranking | (new; the level-up stage) |
| `bounding.py` | `AgentPermissionGrant`/`AuthorityBoundary` construction (least-privilege, non-broadening) | AI Hiring `BoundaryViolation` idiom |
| `fallback.py` | `FallbackAssignment` chain, re-checked against primary constraints | Model Selection §9 fallback chain |
| `registry.py` | `AgentRegistrySnapshot` container + `evaluate → (eligible, excluded)` | `registry.py` (`ExecutableRegistry`) |
| `explanation.py` | `SelectionExplanation` + deterministic prose rendering | Model Selection §7 |
| `replay.py` | `SelectionReplayRecord`, `replay()`, `counterfactual()` | AI Hiring reconstruction/determinism |
| `fingerprint.py` | digests via `canonical_hash` (`REUSE`) | `fingerprint.py` |
| `api.py` | curated public surface (no logic) | `api.py` |
| `version.py` | `__version__`, `CONTRACT_VERSION = "awc.v1"`, `POLICY_VERSION` | `version.py` |

`[SPEC]` `compose_agents` (in `api.py`) is the composition root that threads the stages; each stage is an
independently testable pure function.

---

## 4. Data flow (the pure pipeline)

```
compose_agents(role_requirements, snapshot, enterprise_constraints, policy, now):
  1. freeze CompositionRequest; compute request_fingerprint (canonical_hash)      [determinism]
  2. for each role_requirement:
        for each AgentProfile in snapshot:
            AgentEligibilityGate.evaluate(profile, role, policy, now) -> AgentEligibilityResult   [Stage 1]
        eligible, excluded = partition by state                                    [total accounting]
        if eligible empty: RoleSelectionDecision(NO_ELIGIBLE_AGENT, reasons)        [no empty success]
        else: AgentScorer.rank(eligible, role, policy) -> ranked                    [Stage 2]
  3. TeamComposer.compose(ranked_by_role, workflow_edges, policy)                   [Stage 3]
        -> enumerate TeamCandidate(s); eliminate on interface/SoD/concentration/correlation
        -> pick best feasible candidate (or partial with flagged roles)
  4. for each assignment: bounding.build_grant(role, agent) -> AgentAssignment      [Stage 4, least-privilege]
        fallback.select(role, eligible, primary) -> FallbackAssignment              [non-broadening]
  5. assemble AgentTeamPlan(assignments, non_agent_dispositions, fallbacks,
        snapshot_digest, policy_version, request_fingerprint, rendered_explanation) [plan_only]
  6. emit SelectionExplanation + SelectionReplayRecord
```

`[SPEC]` The pipeline is total: every agent exits classified for every role; every team option exits chosen or
eliminated-with-reason. There is no path that drops an input silently or invents an output.

---

## 5. Determinism architecture

`[SPEC]`
- **No ambient state.** `now` injected; no `Date`/clock/RNG in the core (Model Selection `states.py` discipline).
- **Snapshot pinning.** The `AgentRegistrySnapshot`, `CompositionPolicy` version, and `EnterpriseAgentPolicy` are
  frozen and digested; the `AgentTeamPlan` records all three digests + `request_fingerprint`.
- **Stable ordering.** Every sort has an explicit tie-break on a stable id (`agent_id`, `role_id`) — never rely on
  set/dict iteration order.
- **Canonical hashing.** All digests via `canonical_hash` (`REUSE` from decision-authority kernel), order-independent.
- **Replay.** `SelectionReplayRecord` + `replay()` re-executes the pure function and must yield a byte-identical
  plan; a digest mismatch is a hard error, not a re-derivation (fail-closed).

---

## 6. Extension / integration seams (all data, never imports)

| Seam | Direction | Shape | Classification |
|---|---|---|---|
| `WorkflowGraphSource` | in | adapter over the Policy Workflow Compiler's governed workflow graph | `COMPOSE` |
| `AgentRegistrySnapshot` | in | frozen provider/agent profiles; provenance owned upstream | `COMPOSE` (+ `ADAPT` H16 shape) |
| `EnterpriseAgentPolicy` / `CompositionPolicy` | in | customer-owned constraints + engine policy-as-data | `SPEC` |
| `AgentTeamPlan` → Agent Runtime | out | maps to a `WorkflowDefinition` of `TaskDefinition`s | `COMPOSE` |
| `assigned_agent` + `authority_scope` → H22 | out | H22's `PortfolioWorkflowEntry` fields (fixed inputs to it) | `COMPOSE` |
| `model_policy_ref` per assignment → Model Selection | out | neutral reference the runtime later resolves | `COMPOSE` |
| binding decision points → Decision Authority | out (by id/hash) | plan marks `HUMAN_AUTHORITY_REQUIRED`; DA decides | boundary |
| action points → ActionGate / Action Clearance | out (by id/hash) | plan bounds permissions; those engines authorize/clear | boundary |
| StoryGraph advisory signals | in (advisory) | `OBSERVE/ESCALATE/UNAVAILABLE` may inform a role's risk input; never a binding block | `COMPOSE` (advisory) |

---

## 7. Why not each obvious alternative placement (`[INFERENCE]`, mirrors the Model Selection ADR)

- **A subsystem of Agent Runtime?** No — binds a cross-cutting policy to one runtime and puts selection inside the
  proposer's trust boundary. The runtime is a *consumer* of the plan (it already has no agent-selection model, only
  an unused `AgentDescriptor`).
- **A subsystem of H22?** No — H22 schedules *already-staffed* workflows; it treats `assigned_agent`/`authority_scope`
  as fixed inputs. Making AWC part of H22 conflates staffing with scheduling.
- **Part of the H16 agentic framework?** No — the `agentic/` tree is the heavily-coupled legacy node
  (`[EXISTING]` packaging audit: "the one heavily-coupled node"). AWC should be a clean leaf that H16 can consume,
  and should *canonicalize* H16's selection concepts outward, not live inside the coupled tree.
- **A product?** No — it is consumed by many products (Procurement, Support, Security, AI Hiring); the terminology
  audit defines that as a capability, not a product.

---

## 8. Failure-domain architecture (fail-closed)

`[SPEC]` Each stage has a defined closed failure: extraction (bad graph → no plan), eligibility (unknown evidence →
`INELIGIBLE`/`INDETERMINATE`), scoring (empty pool → `NO_ELIGIBLE_AGENT`), composition (no feasible team → partial
plan with flagged roles), bounding (over-broad grant → construction error), replay (digest mismatch → hard error).
A degraded AWC produces **less** staffing and **narrower** authority, never more — the safety-monotonic property
(design spec §28).

---

## 9. Observability

`[SPEC]` AWC emits structured, hash-chained audit events per stage (`ADAPT` AI Hiring `HiringDomainAuditEvent`),
each carrying `correlation_id`/`causation_id`, the input digests, and the stage outcome. Because the core is pure,
the `SelectionExplanation` *is* the primary observability surface — a total, deterministic account replayable
offline. No metrics are invented; latency/throughput of the composer itself are runtime concerns outside the pure
core.
