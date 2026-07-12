# Agent Action Admissibility Gate — MVP Specification

**Status:** the focused, buildable product spec. It **supersedes the broad platform framing**
in `ROADMAP.md` (adaptive security orchestration) and `CRITICAL_TRANSITION_GOVERNANCE.md`
(organizational state governance) by narrowing them to a single vendor-neutral product with a
concrete beachhead. Those documents remain the strategic context; this is what gets built.

**Core thesis.** A **vendor-neutral pre-commit admissibility gate at the autonomous-agent
tool-invocation boundary**, initially for **production-infrastructure actions**. The gate
permits a consequential action only when the proposed transition leaves the system inside a
**conservatively enforceable approximation of the safe viability kernel**. It wins by **safely
allowing more legitimate autonomy** than static permissions or approve-everything workflows —
not merely by blocking more actions.

**No new mathematics claim.** This is a new *infrastructure layer*, not a new abstraction. It
applies viability / invariant-preservation (control theory), reachability (attack graphs), and
constraint logic (policy-as-code) to the uniform action boundary of autonomous agents. See §12.

**Evaluation discipline** is inherited from `kill_study/` (preregistration, fair baselines,
paired comparison, mechanical verdict, **practical** effect thresholds `Δ_min`, no post-hoc
goalpost moves). BCVF / USE / SCC are **not** core mechanisms here; see §1 and `BCVF_CONCEPT_DIRECTION.md`,
`USE_CONTRIBUTION_MAP.md`.

---

## 1. Product scope and non-goals

**In scope (the production-infrastructure beachhead):**
- Autonomous coding, operations (DevOps/SRE), and cloud agents.
- Production tool calls issued by those agents.
- Changes to: IAM/permissions, deployments, network exposure, databases, secrets, monitoring/
  logging/security controls, and cloud cost/quota.
- **Pre-commit** enforcement — the gate sits *before* the irreversible external-state change.

**Out of scope (explicitly):**
- Universal organizational governance / horizontal "govern any decision" platform (that is the
  incumbent trap; see `ROADMAP.md` §3 and the Part-9 verdict).
- Behavioral biometrics as a dependency.
- BCVF, USE, or SCC as core mechanisms.
- Healthcare or financial *decision* governance (different invariants, different verticals).
- Autonomous AI *authorization* — AI never authorizes; it is advisory + escalate-only (§7).
- Claims of formal verification over the open world — we build a **conservative
  under-approximation**, not a proof (§3, §12).

**Optional-evidence stance.** BCVF (same-latent estimator disagreement), USE (cross-modal
coordination), anomaly models, and behavioral signals may **later** appear only as *optional
evidence plugins* feeding the escalation decision. The gate must be fully useful with **all of
them removed** — that is the architectural test, and today the answer is yes.

---

## 2. Canonical action envelope

A framework-neutral action object `τ`. The gate operates on this envelope, never on a
vendor-specific call. **Required (R)** vs **Optional (O)** noted per field.

| Field | R/O | Meaning |
|---|---|---|
| `action_id` | R | unique id for this attempted transition |
| `agent_identity` | R | cryptographic identity of the acting agent |
| `agent_runtime` | R | runtime/framework (e.g. MCP host, SDK, custom) |
| `model_provider` | R | model + provider producing the decision |
| `delegator` | R | human or service on whose authority the agent acts |
| `delegation_chain` | R | ordered chain of delegations (who authorized whom) |
| `delegated_objective` | R | the task/purpose the agent was given |
| `tool_server_identity` | R | tool/server the operation targets |
| `operation` | R | the operation (typed; maps to a transition class) |
| `target_resource` | R | resource identifier(s) |
| `arguments` | R | operation arguments (normalized) |
| `credential_privilege_scope` | R | credential + effective privilege being exercised |
| `current_observed_state` | R | relevant current state snapshot |
| `state_freshness` | R | age/source of the state snapshot (§6) |
| `predicted_effects` | O | simulator-produced effects (§6) |
| `requested_deadline` | O | latency budget for the decision |
| `reversibility_class` | R | REVERSIBLE / REVERSIBLE_WITH_COST / IRREVERSIBLE (§10) |
| `rollback_plan` | O | declared rollback, if any |
| `linked_change` | O | ticket / change-request reference |
| `approvals` | O | approvals already collected (§8) |
| `attestation_evidence` | O | device/runtime attestation |
| `policy_version` | R | signed policy version evaluated (§4) |
| `correlation_ids` | R | session/sequence ids for structuring detection (§12) |

**Field discipline.** Required fields must be present and well-formed or the action is
`DENY`ed (fail-to-safe on malformed envelopes). Optional fields *raise* achievable assurance
(e.g. a validated `rollback_plan` can move an action from escalation to auto-admit) but their
absence never *lowers* a hard requirement.

**MCP mapping (integration, not dependency).** An MCP `tools/call` maps to the envelope:
server→`tool_server_identity`, tool name→`operation`, params→`arguments`, session→
`correlation_ids`, host identity→`agent_runtime`/`agent_identity`. **The core model is
MCP-independent**: adapters also map raw SDK tool calls, API-gateway requests, and
credential-broker grants into the same envelope (§9).

---

## 3. State-transition and viability model

- **State space `S`** — the (partial, distributed, possibly stale) observed state relevant to
  the action's resource and its dependencies.
- **Hard safe set `A = { s ∈ S : φ₁(s) ∧ … ∧ φₙ(s) }`** — the conjunction of hard invariants
  (§4). Non-compensatory.
- **Requested transition `τ: S ⇀ S`** — the envelope's operation applied to state.
- **Conservative viability approximation `Viab̂(A)`** — a set we can *certify* is viable: states
  from which enforced future gate decisions can keep the system in `A`.

**Corrected admissibility condition** (viability, not invariance):

```
τ(s) is AUTOMATICALLY ADMISSIBLE   only if   τ(s) ∈ Viab̂(A)
```

We do **not** require that no unsafe state is reachable (that is the invariance condition,
`Reach(τ(s)) ⊆ A`, which is too strict and would deny almost everything — an admin *can* reach
unsafe states; later gate decisions are the control that keeps the system safe). We require that
after committing `τ`, **safety remains maintainable under the gate's own future enforcement.**

**Three regions** (this is the whole product in one picture):

```
τ(s) ∈ Viab̂(A)              → SAFE, auto-admissible            (allow)
τ(s) ∉ Viab̂(A) and ∉ Unsafe → UNCERTAIN (outside the certified kernel, not proven unsafe) → ESCALATE
τ(s) violates a hard φ_i     → DEMONSTRABLY UNSAFE              (deny)
```

**Exact `Viab(A)` is unavailable** in open cross-domain systems (the future transition dynamics
are not fully known). `Viab̂(A)` is therefore a **conservative under-approximation**: everything
in `Viab̂(A)` is genuinely viable; the gap between `Viab̂(A)` and the true `Viab(A)` is exactly
the **escalation region** (uncertain → human). The tiered engine (§5) *is* the machinery that
computes `Viab̂(A)`.

**Robust viability for high-assurance actions.** For irreversible / high-blast-radius classes,
require `τ(s) ∈ Viab̂_robust(A)`: viability must hold under **bounded adversarial/uncertain
behavior between gate checks** (the discriminating-kernel form). This shrinks the auto-admit
region for the most dangerous actions, pushing more of them to escalation — deliberately.

---

## 4. Hard invariants and soft objectives

**Minimal invariant language.** Invariants are typed predicates over `(envelope, current_state,
predicted_effects)`. Two strictly separated classes:

**Hard invariants `φ_i(s) ∈ {0,1}`** — deterministic, human-ratified, versioned,
**non-compensatory**, and **not overridable by AI confidence**. A single `false` → `DENY` or
mandatory escalation, regardless of any score.

Examples:
- an agent **cannot broaden its own permissions** (privilege monotonicity);
- **sender cannot approve its own** critical action (segregation of duties);
- **deletion requires a verified, restorable backup**;
- **production secrets cannot be exported** to non-approved sinks;
- **security monitoring/logging cannot be disabled** without independent approval;
- **critical actions require fresh evidence** (`state_freshness` within class bound).

**Soft objectives `u_j(s) ∈ ℝ`** — advisory, scored, uncertain, contestable. They **may trigger
escalation** but **cannot silently become hard policy**. Examples: "action consistent with
delegated objective," "no apparent contradiction with an open change," "scope expansion within
norm." AI may *interpret* soft objectives and *propose candidate* hard invariants, but a human
must **ratify** any promotion soft→hard; AI-inferred invariants remain soft until ratified.

**Policy provenance & root-of-trust.** The policy set `{φ_i}` and its version are:
- **signed** by a policy root-of-trust held **out-of-band** from the agents/runtime it governs
  (a policy change is itself a governed critical transition — avoid the bootstrap circularity by
  rooting policy authority outside the governed plane);
- **reviewed** and **versioned**; every decision records `policy_version`;
- **rollback-able** to a prior signed version;
- never mutated by the gate's own AI components.

---

## 5. Tiered consequence engine (the `Viab̂(A)` approximation)

Three tiers, in increasing uncertainty and decreasing authority. **They collectively compute
`Viab̂(A)`**; the region not confidently covered by Tier 1 + trusted Tier 2 **is** the escalation
region.

**Tier 1 — exact local checks (authoritative; can support auto-admit):**
- policy predicates over the envelope; permission deltas (does this widen authority?);
- spending/quota limits; destructive-operation detection; explicit resource invariants.
- Deterministic, cheap, high-confidence. A Tier-1 hard-invariant violation is dispositive.

**Tier 2 — bounded consequence / blast-radius (authoritative when fidelity is trusted):**
- dependency graph → reachable resources, downstream services, affected users/accounts;
- permission-expansion closure (transitive authority the change unlocks);
- rollback availability; **sequence effects** (this action combined with recent ones, via
  `correlation_ids` — structuring detection);
- outputs a bounded blast-radius estimate with a **coverage** measure.
- Trusted Tier-2 evidence (bounded, fresh, high-coverage) can support auto-admit *inside* the
  computed bound; outside the bound → escalate.

**Tier 3 — advisory semantic analysis (escalate-only; never authoritative):**
- action vs delegated objective; justification consistency; hidden side-effect hypotheses;
- unusual scope expansion; contradiction with an open project/ticket.
- Model-dependent and **potentially attacker-influenced** (the input text/objective is
  adversary-controllable). **Tier 3 may only escalate or annotate — never admit, never lower
  assurance.** Under prompt injection its worst case is spurious escalation (friction), not
  spurious admission — an acceptable failure mode by construction.

Rule: **Tier 1 + trusted Tier 2 → the certified `Viab̂(A)` → auto-admit. Tier 3 and the
uncovered region → escalate. Hard-φ violation → deny.**

---

## 6. Simulation and dry-run contract

**Simulation is evidence, not ground truth.** Every simulator that contributes must return a
structured report:

- `modeled_effects` — what it predicts changes;
- `coverage` — fraction/scope of effects it claims to model;
- `assumptions` — what it assumed (versions, state, isolation);
- `confidence` — calibrated where possible;
- `freshness` — age of the state it simulated against;
- `omitted_dependencies` — known gaps;
- `plan_execution_divergence_risk` — how likely plan ≠ real execution;
- `rollback_confidence` — confidence the declared rollback works.

**Fidelity classes:** `HIGH` (authoritative for its covered scope), `MEDIUM` (supporting,
requires corroboration), `LOW`/`UNKNOWN` (annotative only). **Low/unknown-fidelity simulation
cannot independently authorize a consequential transition** — it may inform escalation but not
replace a Tier-1/2 check. This closes the simulation-fidelity failure mode (the gate green-lights
because dry-run looked safe, but reality diverged).

**Post-commit calibration (required).** After a committed action, compare **predicted vs actual**
effects; feed the divergence back to down-rate the simulator's future fidelity class. Simulators
earn trust empirically, like every other component.

Examples: `terraform plan`, cloud IAM policy simulator, Kubernetes `--dry-run=server`, database
transaction preview/`EXPLAIN`, cloud-policy (SCP/Org-policy) simulation.

---

## 7. Decision outcomes and assurance policy

**Outcome set:**
- `ALLOW`
- `ALLOW_WITH_CONSTRAINTS` (narrowed scope/args, time-boxed, rate-limited)
- `SIMULATE_OR_REPLAN` (require a passing high-fidelity simulation or a revised action)
- `REQUEST_ADDITIONAL_EVIDENCE` (freshness, attestation, rollback proof)
- `REQUIRE_HUMAN_APPROVAL` (§8)
- `DENY`

**Non-compensatory hard gates.** Any hard-φ violation or any `FAIL` from a required check forces
`DENY` or `REQUIRE_HUMAN_APPROVAL` and **cannot be offset** by high soft scores or model
confidence. The composition is: hard gates first; soft/advisory only *within* the region hard
gates leave open.

**AI boundary (safety-monotone).** AI may only: identify concerns; extract structured evidence
from unstructured inputs; propose consequence hypotheses; **increase** required assurance;
recommend safer alternatives. AI may **never**: override a failed invariant; **lower** required
assurance; approve a critical action; modify policy. Its influence is logged and bounded to
escalation.

**Escalation rule inputs:** `reversibility_class`, blast-radius (Tier 2), `state_freshness`,
simulation fidelity, and confidence. Higher irreversibility / larger blast radius / staler
evidence / lower fidelity → higher required assurance tier, monotonically.

---

## 8. Human approval handshake

- **Eligible approvers:** defined per transition class; must satisfy **segregation of duties**
  (approver ≠ requester/delegator; approver in an independent authority line).
- **Independent approval:** high-assurance classes require ≥2 independent approvers
  (dual-control); collusion resistance scales with the required N.
- **Approval expiration:** approvals are time-boxed; stale approvals are invalid.
- **Binding to the exact action:** approval is cryptographically bound to a **hash of the
  canonical action envelope + `policy_version`**, not to a ticket title. Any change to arguments,
  target, scope, or policy version **invalidates** the approval (no "approve a benign action,
  swap the payload").
- **Break-glass/emergency path:** a fast path with *stronger* post-hoc audit, tighter time-box,
  mandatory review, and automatic alerting — never a silent bypass.
- **Post-event review:** every human-approved critical action is reviewed; approvals feed audit.

---

## 9. Enforcement chokepoints

The gate is only real where the agent **cannot bypass it**. Implementation options (composable):

- **MCP gateway/proxy** — intercept `tools/call` at the protocol boundary (vendor-neutral;
  primary opportunity).
- **Agent-tool SDK wrapper** — for non-MCP frameworks.
- **API gateway** — for direct cloud/API calls.
- **Credential broker** — the gate mints/withholds short-lived credentials, so an unapproved
  action has no usable credential (strong, bypass-resistant).
- **Service-mesh sidecar** — network-layer interception.
- **Kubernetes admission controller** — for cluster-state changes.
- **CI/CD gate** — for deploy/IaC paths.
- **Privileged execution service** — actions run only via a brokered, gated executor.

**Bypass resistance (non-negotiable).** Enforcement is valid **only when the agent cannot reach
the effect via alternate credentials or direct network access.** The strongest realizations
combine a **credential broker** (no credential without admission) with network egress control —
so the chokepoint is not merely advisory. Envelope-only interception without credential/network
control is *monitoring, not enforcement*, and must be labeled as such.

**Fail behavior by action class:**
- Reversible, low blast radius → **fail-open with audit** acceptable (availability-preserving).
- Irreversible / high blast radius → **fail-closed** (deny on missing gate/evidence).
- Ambiguous / evidence-unavailable → **fail-to-human** (escalate), never silent allow.

**Protocol-absorption risk.** MCP is an **opportunity, not the architecture.** If admissibility
hooks become native to the protocol/runtime, the neutral chokepoint can be disintermediated.
Mitigations: keep the **policy and action model runtime-neutral** (works across MCP + non-MCP);
treat open-protocol integration as commodity and locate the **defensible value in enforcement +
policy authority + cross-runtime neutrality + calibrated consequence analysis**, not in the
protocol adapter. See §12 timing/absorption risk.

---

## 10. Ten concrete production-infrastructure transitions

Each: current state → requested transition → hard invariants → consequence → reversibility →
simulation → required evidence → possible outcomes → human-approval rule.

**T1 — Grant IAM administrator permission.**
- State: principal has role R (< admin). Transition: attach admin/privileged policy.
- Hard φ: agent **cannot broaden its own** authority; no privilege grant that lets grantee
  re-grant unboundedly (monotonic-authority); SoD (grantee ≠ approver).
- Consequence (T2): transitive permission closure; resources newly reachable; blast = whole account.
- Reversibility: REVERSIBLE_WITH_COST (revoke, but actions taken meanwhile may persist).
- Simulation: IAM policy simulator (HIGH for reachability).
- Evidence: fresh IAM state; justification; rollback (revoke plan).
- Outcomes: DENY (self-grant); REQUIRE_HUMAN_APPROVAL (else). **Approval: dual-control.**

**T2 — Create/modify a production deployment.**
- State: service at version v. Transition: deploy v′ / change replicas/config.
- Hard φ: image from approved registry+signature; no disabling of health/rollback; blast within
  declared service boundary.
- Consequence: dependent services; traffic exposure; rollback availability.
- Reversibility: REVERSIBLE (if prior version retained) else REVERSIBLE_WITH_COST.
- Simulation: K8s server-dry-run (HIGH); canary plan.
- Evidence: signed artifact; retained previous version; freshness.
- Outcomes: ALLOW (signed + canary + rollback present) / ALLOW_WITH_CONSTRAINTS (canary only) /
  escalate. **Approval: none if all hard φ pass + HIGH-fidelity dry-run; else single approver.**

**T3 — Delete a production database / storage resource.**
- State: resource exists with data. Transition: delete/destroy.
- Hard φ: **verified restorable backup exists** and recovery tested within window; not the last
  replica of an in-use resource.
- Consequence: downstream readers; irreversibility of data loss.
- Reversibility: **IRREVERSIBLE** (data) → `Viab̂_robust` required.
- Simulation: dependency/reference scan; backup-restore verification.
- Evidence: backup id + restore proof + freshness.
- Outcomes: DENY (no verified backup); REQUIRE_HUMAN_APPROVAL always for irreversible.
  **Approval: dual-control + break-glass disallowed for last-replica.**

**T4 — Modify firewall / network exposure.**
- State: resource private. Transition: open port / public ingress / widen CIDR.
- Hard φ: no public exposure of resources tagged sensitive; no `0.0.0.0/0` on admin ports;
  monitoring remains on.
- Consequence: newly reachable attack surface; exposed dependent services.
- Reversibility: REVERSIBLE (close), but exposure window is real.
- Simulation: cloud network-reachability analyzer (HIGH).
- Evidence: current exposure map; freshness; justification/ticket.
- Outcomes: DENY (sensitive/public); escalate (widening); ALLOW (narrowing/closing).
  **Approval: single approver for widening; auto for narrowing.**

**T5 — Read / export a production secret.**
- State: secret in vault. Transition: read/export to sink.
- Hard φ: **secrets cannot be exported** to non-approved sinks; no bulk secret enumeration;
  purpose bound to delegated objective.
- Consequence: credential blast radius if leaked; downstream systems the secret unlocks.
- Reversibility: **IRREVERSIBLE** (a read secret is compromised) → rotate-after semantics.
- Simulation: n/a (read is the effect) — rely on Tier 1/2.
- Evidence: sink approval; scope (single vs bulk); freshness.
- Outcomes: DENY (export/bulk); REQUIRE_HUMAN_APPROVAL for any prod-secret read.
  **Approval: single approver + mandatory post-read rotation policy.**

**T6 — Disable monitoring / logging / security control.**
- State: control enabled. Transition: disable/suspend.
- Hard φ: **security monitoring cannot be disabled without independent approval**; never disable
  the audit path of the gate itself.
- Consequence: blinding of detection; enables subsequent unobserved actions (sequence risk).
- Reversibility: REVERSIBLE, but the blind window is the attack.
- Simulation: n/a; Tier 1/2 + sequence check (T2).
- Outcomes: DENY (gate's own audit); REQUIRE_HUMAN_APPROVAL (else), time-boxed re-enable.
  **Approval: dual-control + auto re-enable deadline.**

**T7 — Run a production database mutation.**
- State: table/rows. Transition: UPDATE/DELETE/DDL.
- Hard φ: no unbounded mutation (must have WHERE/limit); DDL on critical tables requires backup;
  no disabling of constraints.
- Consequence: rows affected (from preview); dependent app invariants.
- Reversibility: REVERSIBLE_WITH_COST (if transaction + backup) else IRREVERSIBLE.
- Simulation: transaction preview / `EXPLAIN` + affected-row count (HIGH/MEDIUM).
- Evidence: preview row count within bound; backup; freshness.
- Outcomes: ALLOW_WITH_CONSTRAINTS (bounded, in-transaction) / escalate / DENY (unbounded).
  **Approval: single approver above a row/impact threshold.**

**T8 — Rotate credentials / keys.**
- State: key K active. Transition: rotate/revoke.
- Hard φ: no orphaning of live dependents without cutover; not rotating the gate's own trust root
  outside the policy-root process.
- Consequence: dependent services requiring K; brief unavailability.
- Reversibility: REVERSIBLE_WITH_COST.
- Simulation: dependent-usage scan.
- Evidence: dependents map; cutover plan.
- Outcomes: ALLOW (cutover present) / escalate (live dependents) / DENY (trust-root outside process).
  **Approval: single approver if live dependents.**

**T9 — Increase cloud spending / quota significantly.**
- State: limit L. Transition: raise to L′ ≫ L.
- Hard φ: spending-limit invariant; delta within class cap; not self-approved.
- Consequence: financial blast radius; runaway-cost risk (esp. autoscaling/agent loops).
- Reversibility: REVERSIBLE (lower again) but spend incurred is IRREVERSIBLE.
- Simulation: cost projection.
- Evidence: justification; projected spend; budget owner.
- Outcomes: ALLOW (small delta) / REQUIRE_HUMAN_APPROVAL (large) / DENY (self-approved).
  **Approval: budget-owner approval above threshold.**

**T10 — Send externally visible customer/status communication.**
- State: no message sent. Transition: send external comms.
- Hard φ: **content from an approved template/approval**; no unapproved free-text to customers;
  rate/scope limits; not impersonating.
- Consequence: reputational/legal; irreversible once delivered.
- Reversibility: **IRREVERSIBLE** (message delivered).
- Simulation: n/a; content policy check (Tier 1) + Tier 3 advisory consistency.
- Evidence: approved content ref; audience scope.
- Outcomes: DENY (unapproved free-text/mass) / REQUIRE_HUMAN_APPROVAL (else).
  **Approval: comms-owner approval; dual-control for mass audience.**

---

## 11. Baselines, evaluation, and kill criterion

**Baselines (the gate must beat these, fairly):**
- **A.** Static tool allowlist.
- **B.** RBAC / least-privilege tool permissions.
- **C.** Conventional policy-as-code (OPA/Cedar; static, local predicates).
- **D.** Human approval for **every** consequential action.
- **E.** Vendor-native agent guardrails.
- **F.** Proposed admissibility gate (this spec).

**Primary frontier:** **unsafe commits prevented vs legitimate automation blocked/delayed.**
The differentiating claim is *not* "blocks more" (D blocks most). It is: **at a fixed unsafe-
prevention level, F auto-admits materially more legitimate actions than C/D** via simulation +
blast-radius + targeted escalation.

**Required metrics** (held-out; discipline from `kill_study/`):
- unsafe-action prevention rate;
- legitimate-action **automatic-admission** rate (the value metric);
- false-escalation rate (legit actions needlessly escalated);
- time-to-decision (p50/p95);
- human-review burden (approvals per legit-action-hour);
- simulation-fidelity failure rate (predicted≠actual on committed actions);
- **bypass rate** (actions reaching effect without gate);
- policy coverage (fraction of transition classes with hard invariants);
- rollback success rate;
- damage-weighted residual failures (unsafe commits × impact×irreversibility).

**Operational kill criterion (preregistered, mechanical):**

> The MVP is **NOT_SUPPORTED** unless, on held-out evaluation, F prevents **materially more**
> unsafe *composite* actions than conventional policy-as-code (C) **while automatically admitting
> materially more legitimate actions than approve-everything (D)** — both by a **preregistered
> practical margin `Δ_min`**, with preregistered upper bounds on time-to-decision and
> human-review burden, and a bypass rate below a preregistered ceiling.

Prespecify **practical minimum effects `Δ_min`**, not merely statistical significance (the
`kill_study` n=1024 lesson: a significant-but-negligible effect is a fail). If F cannot beat C on
safety *and* D on autonomy simultaneously within the friction/latency/bypass bounds, the product
thesis is not supported.

---

## 12. Threat model, limitations, staged roadmap

**Threat model — mitigated / shifted / unsolved:**

| Threat | Status | Note |
|---|---|---|
| Compromised agent | **mitigated** | can't exceed brokered credentials / hard φ; still bounded by policy coverage |
| Malicious human delegator | **shifted** | pushed to SoD + approver independence; determined authority abuse persists |
| Colluding approvers | **shifted** | N-party dual-control raises cost; not eliminated |
| Policy poisoning | **shifted** | out-of-band signed policy root; "modify policy" is itself governed → don't self-host trust |
| Prompt injection | **mitigated-to-acceptable** | Tier-3 escalate-only → worst case spurious escalation, not admission |
| Stale state | **unsolved (fundamental)** | freshness bounds + fail-to-human; can't guarantee global freshness |
| Missing evidence | **shifted** | UNAVAILABLE→escalate; attacker can induce to raise friction/DoS |
| Simulator mismatch | **mitigated** | fidelity classes + post-commit calibration; low-fidelity can't authorize |
| Action structuring (multi-call) | **partially mitigated** | Tier-2 sequence analysis via `correlation_ids`; sophisticated splitting persists |
| Direct-tool bypass | **mitigated by design** | valid only with credential-broker + egress control; else monitoring-not-enforcement |
| Stolen credentials | **shifted** | pushed to credential issuance/attestation strength |
| Full endpoint/tool compromise | **unsolved** | below the enforcement layer; needs hardware root of trust |
| Model-vendor/runtime absorption | **strategic risk** | keep runtime-neutral; value in enforcement+neutrality, not the adapter |
| Adoption timing | **strategic risk** | demand is incident-/compliance-driven; early buyers are risk-averse verticals |

**Staged build plan:**
- **Stage 0** — this document: schema + ten transitions (done).
- **Stage 1** — deterministic **policy-only gateway** on one tool surface (Tier 1 + hard φ + credential broker) — real enforcement, no AI, no simulation.
- **Stage 2** — **simulation + blast-radius** integration (Tier 2, fidelity classes, post-commit calibration).
- **Stage 3** — **human approval + signed audit** (envelope-hash binding, SoD, break-glass).
- **Stage 4** — **advisory semantic reasoning** (Tier 3), escalate-only, injection-hardened.
- **Stage 5** — **multi-runtime**: MCP + non-MCP adapters (SDK, API gateway, admission controller).
- **Stage 6** — **operational comparative evaluation** (§11) with the preregistered kill criterion.

**Can-prove / cannot-prove.**
- *Can prove (empirically, on the beachhead):* the gate prevents specific unsafe composite infra
  actions; it auto-admits more legitimate actions than approve-everything at a fixed safety level;
  enforcement is bypass-resistant under the credential-broker realization; simulators are
  calibrated by post-commit divergence.
- *Cannot prove:* safety over the open world; completeness of invariants; freshness of global
  state; resistance to full endpoint compromise; that `Viab̂(A)` equals `Viab(A)`.

**Explicit no-novel-math claim.** This introduces **no new mathematics.** It is an infrastructure
layer built from viability/invariant-preservation (control theory), reachability (attack graphs),
and constraint logic (policy-as-code), applied to the uniform agent tool-invocation boundary.

**Vendor-neutrality thesis.** The defensible position is a **vendor-neutral pre-commit gate at
the tool-invocation boundary** governing agents on any model/runtime — the "neutral layer in a
multi-vendor world" (Okta precedent). Value lives in **enforcement + policy authority +
cross-runtime neutrality + calibrated consequence analysis**, not in any protocol adapter.

**Timing & absorption risks (restated as first-class).** (1) Demand is **incident- or
compliance-driven**; the market may lag the architecture. (2) **Protocol/runtime absorption** —
if admissibility becomes native to MCP or model runtimes, the chokepoint erodes; stay
runtime-neutral and win on enforcement + neutrality, not the adapter.

**Optional-intelligence earns its place.** Every optional component — BCVF, USE, anomaly models,
semantic reasoning — must pass the **same incremental-value test** (§11 discipline) against the
gate-without-it, or it is dropped. The core viability gate must remain useful with all optional
intelligence removed.
