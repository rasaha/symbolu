# Agent Workforce Composer — Selection & Composition Policy

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
Claim labels per design spec §1. The procedure is **deterministic over a frozen snapshot** and mirrors the verified
two-stage discipline of `ugence_model_selection` (`[EXISTING]`), extended with a team-composition stage.

---

## 1. Signature and invariants

```
compose_agents(
    role_requirements: Sequence[WorkflowRoleRequirement],
    agent_registry_snapshot: AgentRegistrySnapshot,
    enterprise_constraints: EnterpriseAgentPolicy,
    composition_policy: CompositionPolicy,
    *, now: float,
) -> AgentTeamPlan
```

**Invariants (each is an executable acceptance test — see assurance plan):**
- **I1 Constraint supremacy** — no preference score may promote an agent that fails any hard constraint; elimination
  is absolute and precedes scoring. (`[EXISTING]` Model Selection §2.3-1.)
- **I2 Governance precedence** — `EnterpriseAgentPolicy` veto > capability/role constraints > optimization scores;
  a separate veto plane, not "more weights". (`[EXISTING]` Model Selection §11.3–11.4.)
- **I3 Explainability totality** — every agent exits `eliminated[]` or `scored[]` for every role; no silent drops.
- **I4 No empty success** — empty eligible pool ⇒ `NO_ELIGIBLE_AGENT`, never an invented pick.
- **I5 Non-broadening** — no grant/fallback exceeds the role's `authority_ceiling` or `prohibited_permissions`.
- **I6 Determinism** — same frozen inputs ⇒ byte-identical plan + digest; `now` injected; stable tie-breaks.
- **I7 Humility** — a step may resolve to a `NonAgentDisposition`; AWC never assumes an agent is required.

---

## 2. The ten-step procedure

`[SPEC]`

```
STEP 0 — FREEZE & CLASSIFY
  freeze CompositionRequest; request_fingerprint = canonical_hash(...)
  extract_roles(workflow_graph): each node -> WorkflowRoleRequirement OR NonAgentDisposition
     deterministic-control node   -> DETERMINISTIC_SERVICE_PREFERRED
     binding-decision gate        -> HUMAN_AUTHORITY_REQUIRED
     exact-action-auth node       -> (not a role; downstream action role gets bounded permission)
     human-review node            -> HUMAN_REVIEW_REQUIRED
     agent-eligible node          -> WorkflowRoleRequirement
  (missing source node -> fail-closed; absent data_classification/authority_ceiling -> most-restrictive + flag)

STEP 1 — HARD ELIMINATION (per role, per agent) — never ranks
  for role in role_requirements (that are agent-eligible):
    for agent in snapshot.profiles:
      conditions = [
        capability_present_with_sufficient_provenance,   # measured/observed unless policy allows declared
        input_output_contract_compatible,
        provider_approved (enterprise veto),
        data_residency_ok, data_classification_ok,
        permission_isolation_sufficient,
        authority_requirements <= role.authority_ceiling,
        all agent tools approved,
        projected_cost <= role.maximum_cost AND enterprise hard ceiling,
        latency <= role.maximum_latency AND SLA,
        measured_quality >= role.minimum_quality,
        version_status trusted & not expired & not disabled,
        no prohibited_permission required,
      ]  # each tagged CRITICAL_GOV | CRITICAL_OP | OPERATIONAL, each with evidence_ref
      state = aggregate(conditions)   # ExecutionGate algebra (design spec §12)
      record AgentEligibilityResult(state, conditions, reasons)
    eligible = [a for a in agents if result.selectable]     # ELIGIBLE | CONDITIONALLY_ELIGIBLE
    excluded = agents - eligible                            # recorded (I3)

STEP 2 — RANK ELIGIBLE (per role) — only over eligible
  if eligible empty: RoleSelectionDecision(NO_ELIGIBLE_AGENT, reasons); continue    # I4
  for agent in eligible:
    quality = quality_of(agent, role)      # from measured/observed evidence; NO inference inside AWC
    utility = Σ w_d * normalized(dimension_d)   # quality, domain_fit, reliability, -cost/cref, -latency/lref,
                                                #   security, integration, observability, historical_outcome
             - w.conditional_penalty if CONDITIONALLY_ELIGIBLE
    score[agent] = round(utility, 4)
  ranked = sort(scored, key=(-score, agent_id))   # deterministic tie-break (I6)

STEP 3 — COMPOSE TEAM — level-up stage
  enumerate TeamCandidate archetypes:
    A_generalist: fewest agents covering most roles
    B_specialist: per-role best
    C_hybrid:     deterministic services where sufficient + specialists elsewhere
  for candidate in candidates:
    hard team checks (any fail -> eliminate candidate, record):
      interface_compatibility(all producer->consumer edges)       # INTERFACE_INCOMPATIBLE
      no permission conflict on shared resource
      no data-classification-lowering across a residency/class boundary
      cumulative_cost <= workflow ceiling ; cumulative_latency <= workflow ceiling
      separation_of_duties(candidate) ok                          # SEPARATION_OF_DUTIES_VIOLATION
      authority_concentration(candidate) <= ceiling               # AUTHORITY_CONCENTRATION_EXCEEDED
      provider_concentration(candidate) <= max_share (hard if business-critical)  # PROVIDER_CONCENTRATION_EXCEEDED
    team_score = policy.team_objective(candidate)   # applies composition_bias C>B>A by default (overridable)
  chosen = best feasible candidate ; if none feasible -> partial plan, offending roles flagged (never fabricate)

STEP 4 — BOUND PERMISSIONS & AUTHORITY (per assignment)
  grant = least_privilege(role.required_permissions ∩ agent capabilities − role.prohibited_permissions)
          each permission cites its WorkflowRoleRequirement       # construction fails on prohibited (I5)
  boundary = AuthorityBoundary(role.authority_ceiling, reachable_resources, consequential_tools)
  assignment = AgentAssignment(role, agent, grant, boundary, model_policy_ref?)

STEP 5 — FALLBACK (per role)
  fallback_chain = ordered eligible agents ≠ primary, each re-passing STEP 1 hard constraints & authority_ceiling,
                   preferring a different provider/model/region (design spec §20); never more permissive (I5)
  if none: apply role.fallback_behavior (ESCALATE_TO_HUMAN | HALT_ROLE | PROCEED_WITHOUT_FALLBACK), record

STEP 6 — ASSEMBLE PLAN
  AgentTeamPlan(assignments, non_agent_dispositions, fallbacks, chosen.id, alternatives, snapshot_digest,
                policy_version, request_fingerprint, rendered_explanation, plan_only=True)

STEP 7 — EXPLAIN         SelectionExplanation: per-role eliminated[]+scored[], team rationale, alternatives, residual risk
STEP 8 — REPLAY RECORD   SelectionReplayRecord: fingerprints + digests + now
STEP 9 — (caller) human approval before any consequential handoff; then optional runtime handoff as data
```

---

## 3. Hard constraints vs preferences (the resolution rule)

`[SPEC]` (Model Selection §3.2, lifted.) A dimension is a **hard constraint** iff a wrong-side value makes the agent
*impermissible* for **this** role; a **preference** iff all survivors are acceptable but some are better. The split
is resolved **per requirement from the role's facets**:

| Dimension | Hard when… | Preference when… |
|---|---|---|
| latency | interactive/real-time role with `maximum_latency` | batch role (rank by latency) |
| cost | enterprise hard ceiling / role `maximum_cost` | otherwise (rank by cost) |
| capability | `required_capabilities` | `optional_capabilities` (adds score) |
| residency / data-classification | always hard (governance veto) | never |
| provider | on the enterprise allow/forbid list | otherwise (security-posture score) |
| quality | below `minimum_quality` | above threshold (rank by quality) |

A preference score can **never** resurrect an agent eliminated by a hard constraint (I1).

---

## 4. Team objective and composition bias

`[SPEC]` `CompositionPolicy.team_objective` scores a feasible `TeamCandidate` over: aggregate measured quality,
cumulative cost, cumulative latency, observability, SoD strength, authority-dispersion, provider diversity, and
handoff simplicity. `composition_bias` sets the default preference order among archetypes; the `[PROPOSED]`,
`[UNVALIDATED]` default where governance constraints bind is **C (hybrid) > B (specialist) > A (generalist)** —
prefer a deterministic service or a bounded specialist over a single high-authority generalist. The policy is data;
an enterprise may invert the bias (e.g. cost-first favors A). The engine only **reports and applies** the policy.

---

## 5. Worked example — Procurement approval

`[SPEC]` Compiled workflow steps → extraction:

| Step | Extraction result | Why |
|---|---|---|
| 1 Validate request | `DETERMINISTIC_SERVICE_PREFERRED` | schema/threshold rules suffice; deterministic is safer |
| 2 Check supplier | Supplier-Risk **role** | needs domain reasoning over evidence |
| 3 Check budget | Budget-Analysis **role** (or deterministic if pure lookup) | facet-dependent |
| 4 Prepare recommendation | Recommendation **role** (advisory) | produces HOLD/PASS recommendation, not a decision |
| 5 Obtain human approval | `HUMAN_AUTHORITY_REQUIRED` | binding decision → Decision Authority; **no AI role** |
| 6 Exact purchase authorization | (not a role) | **ActionGate** authorizes the exact action |
| 7 Execute supplier action | Purchase-Action **role**, narrowly bounded | may execute approved ERP update only, post-ActionGate + Action Clearance |
| 8 Reconcile result | Reconciliation **role** (or deterministic) | facet-dependent |

Eligibility (illustrative, over synthetic agents): a `Supplier-Risk` agent claiming the capability **declared-only**
is eliminated `INSUFFICIENT_CAPABILITY_PROVENANCE` (no measured/observed evidence); an agent whose provider is off
the enterprise allow-list is eliminated `PROVIDER_NOT_APPROVED`; an agent requiring an ERP-write permission for the
`Recommendation` role is eliminated `PROHIBITED_PERMISSION_REQUIRED`.

Team composition: SoD forbids the same agent holding both `Recommendation` and `Purchase-Action` (would let one
agent recommend and execute) → `SEPARATION_OF_DUTIES_VIOLATION` if a generalist (Option A) is tried; the composer
falls back to a specialist/hybrid team. Bounded grants:
- Supplier-Risk: read supplier records; **no** ERP write, **no** approval.
- Recommendation: read case; **recommend HOLD/PASS**; **may not decide**.
- Purchase-Action: execute the **approved** ERP update only, after ActionGate ALLOW + Action Clearance CLEAR;
  authority ceiling = single approved purchase; **no** approval permission.

**Counterfactual demo — "customer data must remain in India".** Add `residency_constraints={IN}` to the relevant
roles (or an `EnterpriseAgentPolicy.residency_rules` update) and re-run `compose_agents`. Deterministically:
non-IN-deployed agents are eliminated `DATA_RESIDENCY_VIOLATION`; the composer recomposes from the remaining IN
agents (or returns `NO_ELIGIBLE_AGENT` for a role with no IN option), and the `PlanDiff` reports the replaced agents
and the cost/latency delta. Exact and replayable (design spec §26).

---

## 6. Worked example — Customer-support escalation

`[SPEC]` Roles: **classification** (read-only ticket features), **knowledge-retrieval** (read-only KB scope),
**response-drafting** (produce draft; no send permission), **escalation** (route to human). The binding
refund/credit **decision** is `HUMAN_AUTHORITY_REQUIRED` (Decision Authority). The reply-**send** action is a
narrowly bounded permission on the drafting/escalation assignment and passes ActionGate at runtime. SoD: the drafting
agent may not also hold the send permission for a consequential (refund) reply — that routes through human authority
+ ActionGate. Fallback: a second retrieval agent on a different provider (avoid correlated failure).

---

## 7. Worked example — Cybersecurity incident triage

`[SPEC]` Roles: **evidence-collection** (read-only across security telemetry), **threat-analysis** (reason over
collected evidence). **StoryGraph** provides *advisory* sequence-risk input (`OBSERVE/ESCALATE/UNAVAILABLE`) the
analysis role may consume as a risk facet but must never treat as a binding block. **Containment actions** (isolate
host, revoke credential) are `HUMAN_AUTHORITY_REQUIRED` + ActionGate; the plan grants the analysis agent **no**
containment permission (SoD) and bounds the collection agent to read-only scopes. If the highest-severity host has
no IN-region collection agent under a residency constraint, that role returns `NO_ELIGIBLE_AGENT` rather than
silently using a non-compliant agent.

---

## 8. Determinism & snapshot pinning (restated as procedure)

`[SPEC]` (1) all inputs frozen into `CompositionRequest`; (2) `now` injected; (3) every sort tie-broken on a stable
id; (4) all digests via `canonical_hash`; (5) the plan records `snapshot_digest`, `policy_version`,
`enterprise_policy_digest`, `request_fingerprint`; (6) `replay(record)` re-executes the pure function and must yield
a byte-identical plan — a mismatch is a hard, fail-closed error. This is the precondition for the counterfactual and
assurance machinery.
