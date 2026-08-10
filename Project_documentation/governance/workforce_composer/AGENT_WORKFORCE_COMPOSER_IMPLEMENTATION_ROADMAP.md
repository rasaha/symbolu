# Agent Workforce Composer — Implementation Roadmap

> ## Implementation-Status Correction & Reconciliation Note (2026-08-03)
>
> *Added by AWC Phase 0 (H16 reconciliation). Changes documentation only; no production code.*
> See the ADR: [`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](../../../docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md)
> and the audit set [`docs/audits/agent_workforce_composer_phase0/`](docs/audits/agent_workforce_composer_phase0/).
>
> - **Original assumption:** the Policy Workflow Compiler was *spec-only / not yet implemented*, with no typed
>   `WorkflowIR`, to be integrated "when it ships"; AWC would consume an invented `WorkflowGraphSource`.
> - **Current verified state:** the compiler is **implemented** as the independently packaged
>   `ugence-policy-workflow-compiler` tooling distribution (PR #1303, merge `96afb58a…`). It emits a deterministic
>   **`WorkflowIR`** (`workflow_ir.v1`), capability metadata, assurance artifacts, and content-addressed compiled
>   packages. Document extraction, NLP interpretation, and runtime deployment remain outside its implemented
>   Phase 1 scope.
> - **Architectural consequence:** AWC Phase 1 consumes the **canonical compiler contract** via a thin, versioned,
>   data-only `CompilerWorkflowAdapter` (formerly `WorkflowGraphSource`) — **not** a second workflow
>   representation. The former "spec-only upstream" risk is replaced by
>   **`UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`**.
> - **Documents changed:** all seven `AGENT_WORKFORCE_COMPOSER_*.md`, plus the new ADR and
>   `docs/architecture/agent_workforce_composer_boundaries.json`.
>
> **Reconciled positions all seven documents now agree on:** (1) the Policy Workflow Compiler is implemented;
> (2) AWC consumes the canonical compiler `WorkflowIR`; (3) H16 canonicalization is the accepted ADR decision
> (Option A); (4) AWC is a deterministic, offline, side-effect-free *planning* capability; (5) H16 retains runtime
> coordination and recovery; (6) Model Selection remains separate (models, not agents); (7) Agent Runtime remains
> the executor; (8) H22 remains the scheduler; (9) binding authority (Decision Authority / ActionGate / Action
> Clearance) remains outside AWC; (10) P1 implementation cannot start until the ADR's exit gates pass.


**Status:** `[SPEC]` design / pre-implementation. Companion to `AGENT_WORKFORCE_COMPOSER_DESIGN_SPEC.md`.
Claim labels per design spec §1. **No production code is written in this phase.** This roadmap sequences the work
so the gating design risk (H16 overlap) is resolved *before* any object-model code exists.

---

## 1. Maturity model

`[SPEC]` Follows the repo's H-phase discipline (`[EXISTING]` AI Hiring H0–H6). Distribution SemVer + a separate
capability-maturity label; contract version `awc.v1`. Honest starting label: **research / design-stage,
`production_certified = False`.** No benchmark, validation, competitive, or demand claim attaches to any phase until
evidence exists.

| Phase | Label | Gate to exit |
|---|---|---|
| P0 | Reconciliation & boundary ADR | H16 canonicalization shape + boundaries frozen (no code) |
| P1 | Object model + extraction + eligibility | frozen objects; role extraction; hard-constraint gate; import-boundary test green |
| P2 | Scoring + composition + bounding + dispositions | ranking; team composition; least-privilege grants; five non-agent outcomes |
| P3 | Ledger + replay + counterfactual + assurance corpus | golden corpus; determinism/replay; the constraint-change demo; acceptance criteria met |
| P4+ | Deferred | real registry, runtime handoff, reassignment — each behind its own evidence gate |

---

## 2. Phase 0 — Reconciliation & boundary ADR (the required next step; no production code)

`[SPEC]` **Deliverable:** an ADR (in `docs/architecture/`) that:
1. **Decides the H16 canonicalization shape.** `agentic/agentic_framework/coordination.py` (`AgentProfile`,
   `CapabilityRegistry.candidates_for`, `DelegationContract`, `AuthorityModel`, fallback-across-candidates) and
   `multi_agent.py` already implement the *concepts* AWC needs (`[EXISTING]`, the load-bearing overlap). The ADR
   chooses between: **(a) canonicalize** — AWC owns the deterministic, snapshot-pinned selection/profile primitives
   and the H16 tree re-exports them via a logic-free compatibility facade (the verified
   `execution_gate`→`ugence_model_selection` and `decision_governance`→`ugence_decision_authority` pattern); vs
   **(b) neutral contract** — AWC binds to H16 concepts through a shared contract without moving code.
   **Recommendation `[PROPOSED]`: (a) canonicalize**, because it removes duplication and matches how the platform
   already extracted Model Selection and Decision Authority out of coupled trees.
2. **Freezes four boundaries:** AWC↔H16 (selection vs runtime coordination/recovery + `LLMRouter`), AWC↔Model
   Selection (agents vs models; `model_policy_ref` seam), AWC↔Agent Runtime (`AgentTeamPlan`→`WorkflowDefinition`),
   AWC↔H22 (`assigned_agent`+`authority_scope` produced-vs-consumed).
3. **Confirms the package placement** (capability; `packages/capabilities/agent-workforce-composer/`) and the leaf
   dependency posture.

**Exit gate:** owner sign-off on the canonicalization shape. *Until P0 exits, AWC is `DUPLICATE_RISK` and no code is
written* (design spec §2.3).

---

## 3. Phase 1 — Object model, extraction, eligibility (over synthetic fixtures)

`[SPEC]` Build `models.py`, `states.py`, `reason_codes.py`, `extraction.py`, `eligibility.py`, `registry.py`,
`fingerprint.py`, `version.py`, `api.py` (skeleton). Frozen dataclasses per the object-model doc; role extraction
from a real compiler `WorkflowIR` fixture via the `CompilerWorkflowAdapter`; the hard-constraint eligibility gate (never ranks); the append-only
`EliminationReason` taxonomy; `canonical_hash` digests. Ship the import-boundary test and the distribution-verify
script from day one. **No scoring, no composition yet.** Deliver against the 10–15 synthetic agents.

**Exit gate:** eligibility is deterministic and totally-accounting (I3) over the corpus; boundary test green.

---

## 4. Phase 2 — Scoring, composition, bounding, dispositions

`[SPEC]` Add `scoring.py` (deterministic weighted ranking over eligible only), `composition.py` (interface/SoD/
concentration/correlation checks; A/B/C archetypes), `bounding.py` (least-privilege grants + authority ceilings,
construction-time failure on broadening), `fallback.py` (non-broadening chains), and the five `NonAgentDisposition`
outcomes. `CompositionPolicy` as versioned policy-as-data.

**Exit gate:** I1, I2, I4, I5, I7 hold as tests; the three worked examples produce sane plans with correct non-agent
dispositions.

---

## 5. Phase 3 — Ledger, replay, counterfactual, assurance (the demo)

`[SPEC]` Add `explanation.py` (total, deterministically rendered ledger), `replay.py` (`replay`, `counterfactual`,
`PlanDiff`), and the frozen golden corpus + full assurance suite. Land the flagship demo: change one constraint
("customer data must remain in India") and show deterministic elimination, recomposition, replaced agents, cost/
latency delta, and any `NO_ELIGIBLE_AGENT` role.

**Exit gate:** all acceptance criteria (design spec §36 / assurance §8) pass over the frozen corpus. This is the MVP.

---

## 6. Phase 4+ — Deferred (each behind its own evidence gate) `[DEFERRED]`

Real `AgentRegistrySnapshot` provenance/discovery (owner TBD — open question 2); production telemetry → `observed`
evidence; runtime handoff to Agent Runtime (`AgentTeamPlan`→`WorkflowDefinition`) and H22 (`assigned_agent`+
`authority_scope`); runtime reassignment/adaptation (governed, human-approved, non-broadening); learned ranking
(rank-only, never an enforcement node — `[EXISTING]` Policy Workflow Compiler §7); deeper Policy-Workflow-Compiler
integration beyond the P1 `WorkflowIR` adapter (the compiler is already implemented and consumed);
runtime outcome counterfactuals (needs off-policy estimation). None of these is in the
MVP and none may weaken an invariant.

---

## 7. Major technical risks

`[SPEC]`
1. **H16 duplication** (highest) — mitigated only by P0 canonicalization before code.
2. **Authority-boundary creep** — mitigated by type-enforced `plan_only`, `AuthorityType`-with-no-AI, monotonic
   narrowing, and the import-boundary test.
3. **`[UNVALIDATED]` heuristics** — the authority-concentration measure (§18) and the `minimum_quality` provenance
   bar are deterministic but uncalibrated; keep them advisory / policy-tunable until validated.
4. **`UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`** — the Policy Workflow Compiler is **implemented** and emits
   a canonical `WorkflowIR`; the `CompilerWorkflowAdapter` consumes it directly (no second IR). The risk is pinning
   `workflow_ir.v1` and detecting node/edge/capability enum drift, not upstream absence (open question 5).
5. **Registry trust** — the snapshot's provenance/integrity must be owned upstream; a poisoned snapshot defeats
   selection (open question 2).
6. **`[UNVALIDATED]` demand** — no repository evidence of customer pull; the MVP claims only internal consistency.

---

## 8. Explicitly out of scope for the entire roadmap (until re-chartered)

Agent execution/routing/supervision; binding decisions; action authorization; operational clearance; model routing;
multi-workflow scheduling; agent marketplace; autonomous enterprise-control plane; human recruiting. Each has a
named owner (`AGENT_WORKFORCE_COMPOSER_AUTHORITY_BOUNDARY.md` §3) or is a non-goal.

---

## 9. The exact next action

`[PROPOSED]` Write the **Phase 0 reconciliation ADR** and secure owner sign-off on canonicalizing the H16 selection
concepts into `ugence_agent_workforce_composer`. No object-model code is written until that ADR exits. This
sequencing is the single most important decision in the roadmap: it is the difference between AWC being a clean
canonicalization leaf and AWC being a second, divergent agent-selection implementation.
