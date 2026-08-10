# Agent Workforce Composer — Assurance Plan

> ## Implementation-Status Correction & Reconciliation Note (2026-08-03)
>
> *Added by AWC Phase 0 (H16 reconciliation). Changes documentation only; no production code.*
> See the ADR: [`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md)
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
Claim labels per design spec §1. Assurance is **falsification-first**: the plan's job is to *try to break* each
invariant, not to demonstrate success. No empirical metric is claimed; the MVP's only assertion is internal
consistency, determinism, and replay over a frozen synthetic corpus.

---

## 1. What is being assured

The seven invariants (I1–I7, `AGENT_WORKFORCE_COMPOSER_SELECTION_POLICY.md` §1) plus the authority boundary
(`AGENT_WORKFORCE_COMPOSER_AUTHORITY_BOUNDARY.md`). Each is expressed as an **executable assertion**, following the
verified precedents: AI Hiring `test_h5_determinism` (`[EXISTING]`), Model Selection's constraint-supremacy tests,
StoryGraph's frozen policy-pack conformance, and the repo's import-boundary tests.

---

## 2. Synthetic corpus (frozen, offline)

`[SPEC]`
- **Three reference workflows** as `WorkflowIR` fixtures (real compiler output and/or hand-authored `WorkflowIR`
  of the same type) consumed via the `CompilerWorkflowAdapter`: procurement approval, customer-support escalation,
  cybersecurity incident triage.
- **10–15 synthetic `AgentProfile`s** spanning: multiple providers; declared-only vs measured vs observed evidence;
  IN and non-IN deployment; read-only and consequential tool contracts; overlapping and disjoint capabilities;
  one deliberately over-permissioned agent; one expired-version agent; one stale-evidence agent.
- **Frozen `AgentRegistrySnapshot`, `CompositionPolicy`, `EnterpriseAgentPolicy` fixtures**, each digested.
- **Golden `AgentTeamPlan`s** for each workflow under the base policy — the byte-exact expected outputs.

Every fixture is content-addressed; the corpus digest is committed so drift is detectable.

---

## 3. Invariant test matrix

| Invariant | Falsification attempt (the test tries to make it fail) | Pass condition |
|---|---|---|
| **I1 Constraint supremacy** | Give a hard-constraint-violating agent a maximal preference profile (best quality/cost/latency). | Agent is `INELIGIBLE`; never assigned; appears in `eliminated[]` with the exact reason. |
| **I2 Governance precedence** | Set optimization weights so a forbidden-provider agent would win on score. | Enterprise veto still eliminates it; score never resurrects it. |
| **I3 Total accounting** | Random registry; assert set(eliminated) ∪ set(scored) == set(agents) for every role. | No agent missing from both; no duplicates. |
| **I4 No empty success** | Construct a role no agent can satisfy. | `NO_ELIGIBLE_AGENT` with reasons; no invented pick. |
| **I5 Non-broadening** | Offer a fallback that is strictly more permissive than the primary; offer a grant including a prohibited permission. | Fallback rejected / grant construction raises; ceiling never exceeded. |
| **I6 Determinism** | Run `compose_agents` twice; shuffle input ordering; re-run. | Byte-identical plan + digest; `replay(record)` reproduces it. |
| **I7 Humility** | Each reference workflow. | ≥1 correct `NonAgentDisposition` per workflow (e.g. procurement step 5 = `HUMAN_AUTHORITY_REQUIRED`). |
| **Boundary** | Attempt to import Agent Runtime / H22 / Model Selection / providers / `ai_hiring` / `agentic` from the package. | Import-boundary test fails the build if any appears. |
| **SoD / concentration** | Force a single generalist to cover recommend+execute. | `SEPARATION_OF_DUTIES_VIOLATION` / `AUTHORITY_CONCENTRATION_EXCEEDED`; composer splits or flags. |
| **Plan un-forgeability** | Attempt to attach a decision/authorization field to `AgentTeamPlan`. | Rejected (`plan_only=Literal[True]`, extra forbidden). |

---

## 4. Property-based (generative) tests

`[SPEC]` Generate random-but-well-typed registries, policies, and role sets and assert the invariants hold for **all**
generated inputs (not just the golden corpus):
- **Monotonicity of restriction** — tightening any hard constraint (residency, cost ceiling, provenance bar) never
  *adds* an eligible agent and never *broadens* any grant.
- **Determinism under permutation** — permuting agent/role order never changes the plan.
- **Elimination stability** — an agent eliminated by a hard constraint stays eliminated regardless of scoring weights.
- **Fallback safety** — every emitted fallback re-passes the primary's hard constraints.

---

## 5. Counterfactual (what-if) assurance

`[SPEC]` For each golden plan, apply a catalog of single-input mutations and assert the plan changes in the
**predicted direction**:

| Mutation | Predicted effect |
|---|---|
| Add `residency={IN}` | non-IN agents eliminated `DATA_RESIDENCY_VIOLATION`; recompose or `NO_ELIGIBLE_AGENT`; cost/latency delta reported. |
| Expire an agent's measured evidence | capability degrades to `UNKNOWN`; agent drops from eligible for roles needing that capability. |
| Lower a role's `maximum_cost` below the incumbent | incumbent eliminated `COST_LIMIT_EXCEEDED`; next-best selected or `NO_ELIGIBLE_AGENT`. |
| Forbid the incumbent's provider | eliminated `PROVIDER_NOT_APPROVED`; fallback (different provider) promoted. |
| Remove the only IN agent for a role | role → `NO_ELIGIBLE_AGENT`; no silent substitution. |

The mutation is deterministic and the `PlanDiff` is exact — AWC's planning-time counterfactual has none of the
observability limits of Model Selection's *runtime* counterfactuals (design spec §26). **Runtime outcome
counterfactuals** (did the chosen team actually perform best?) are `[DEFERRED]`.

---

## 6. Replay & audit assurance

`[SPEC]`
- **Replay** — `replay(SelectionReplayRecord)` must reproduce the byte-exact plan; a digest mismatch is a hard error
  (fail-closed), never a re-derivation.
- **Hash chain** — audit events form a valid `previous_event_hash → event_hash` chain (`ADAPT` AI Hiring); a broken
  chain fails `hash_is_valid`.
- **Reconstruction** — `reconstruct(plan_id)` rebuilds requirement→eligibility→score→composition→assignment and
  verifies: every assignment cites a `WorkflowRoleRequirement`; no grant exceeds its ceiling; human approval upheld
  where required; hash chain valid.

---

## 7. Failure-mode assurance (fail-closed)

`[SPEC]` Each closed-failure path (design spec §28) has a test asserting AWC returns **less** staffing / **narrower**
authority, never more:
- malformed/absent workflow graph → no plan (not a guessed plan);
- unknown/stale evidence → `UNKNOWN`/`INELIGIBLE` (not a pass);
- empty eligible pool → `NO_ELIGIBLE_AGENT`;
- no feasible team → partial plan with flagged roles (not a fabricated team);
- absent `data_classification`/`authority_ceiling` → most-restrictive default + review flag;
- over-broad grant construction → error.

---

## 8. Acceptance criteria (v0.1)

`[SPEC]` AWC v0.1 is accepted when, over the frozen MVP corpus, **all** of §3's invariant tests, §4's generative
properties, §5's counterfactual predictions, §6's replay/audit checks, and §7's fail-closed checks pass, and the
import-boundary test forbids every out-of-scope dependency. Explicitly **not** part of acceptance: any performance,
accuracy, competitive, or demand claim — none is made (`[UNVALIDATED]`).

---

## 9. Test scaffolding conventions (`[EXISTING]` patterns reused)

`verify_agent_workforce_composer_distribution.py` (Model Selection / decision-authority pattern) proves the wheel
installs into a clean venv and its public API matches a frozen `public_api.json` snapshot; `test_import_boundaries.py`
(Agent Runtime pattern) enforces the leaf dependency posture; determinism tests follow `test_h5_determinism`;
golden-corpus conformance follows StoryGraph's frozen policy-pack tests.
