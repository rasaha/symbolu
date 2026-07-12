# Roadmap — Adaptive Security Orchestration (consequence-first)

**Status:** the forward plan after the full BCVF → USE → SCC → consequence-gating analysis.
Capstone to `GAP_REGISTER.md`, `COMBINED_ARCHITECTURE_BCVF2_USE_SCC.md`,
`BCVF_CONCEPT_DIRECTION.md`, `USE_CONTRIBUTION_MAP.md`, and `kill_study/`.

---

## 0. How the thesis evolved

```
BCVF (original)   :  can a new detector beat classical detectors?          → refuted (kill study)
middle phase      :  can many detectors beat one detector?                 → no incremental value shown
current thesis    :  minimize expected business damage, regardless of      → the right objective
                     detector quality
```

The center of gravity moved from "build a better behavioral detector" to "use evidence well."
The security outcome now depends far more on **how evidence is used** than on any single
evidence source's performance.

---

## 1. The four-layer architecture

BCVF / USE / SCC are **not** the architecture. The architecture is four layers; those three are
merely Layer-1 evidence producers.

| Layer | Role | Produces / decides | Contents |
|---|---|---|---|
| **L1 Trust Evidence** | produce evidence only, no decisions | calibrated signals + quality | behavioral identity, device identity, **hardware attestation**, **context-bound liveness**, USE coupling, BCVF consistency, network trust, reputation, geolocation |
| **L2 Consequence Model** | how much damage if this action succeeds? | `V_t = f(impact, irreversibility, privilege, recoverability)` | application-specific action/resource map |
| **L3 Decision Engine** | choose the lowest-cost *safe* action | an optimization (below) | expected-loss + friction + op-cost tradeoff under hard constraints |
| **L4 Action Orchestrator** | enact the decision | one of a graded action set | continue / monitor / passive challenge / attestation / behavioral challenge / MFA / supervisor approval / freeze / terminate |

Key property: **no single L1 evidence producer is indispensable.** If an experiment shows a
producer (BCVF same-latent, USE coupling, a 2nd-order feature) adds no incremental value, it is
removed and the rest of the architecture is unchanged. That modularity is a sign of health.

---

## 2. The Decision Engine is the differentiator — as a constrained optimization

Not `Risk = P × Impact` (a score), but **action selection**:

```
choose  a_t = argmin_a  [ ExpectedLoss(a | E_{1:t})  +  λ₁·UserFriction(a)  +  λ₂·OperationalCost(a) ]
        subject to  { security policy, compliance, business rules, latency, UX }   ← HARD constraints
where   ExpectedLoss(a) = P(attack | E_{1:t}) · V_t · ρ_t   (V multi-dim; ρ = recovery-hardness)
```

Why this is right and rich:
- It **unifies enforcement and evidence-gathering**: a cheap attestation/liveness probe is just
  another action `a`, so the evidence-scheduler falls out of the same optimization.
- It chooses the **lowest-cost safe action**, not merely a risk band — trading expected loss
  against friction and operational cost.

Two guardrails (carried from the prior analysis):
- **Hard constraints stay hard.** Compliance, irreversibility, and explicit attestation/liveness
  FAIL are *constraints*, not soft penalties — non-compensatory. No amount of low friction-cost
  buys back a failed hard gate.
- **The new hard problem is cost-model calibration** — putting friction-cost and loss-cost in
  comparable units. More tractable and more within our control than the biometric SNR problem,
  but real; it must be governed and validated, not hand-set.

---

## 3. Strategic positioning (honest)

The pivot to adaptive orchestration is correct about **where value is** — and must be clear-eyed
about **where it competes**:

- **You are no longer competing with BioCatch** (behavioral biometrics, a niche). You are
  entering **adaptive access / policy orchestration** — the most contested space in security:
  Microsoft Conditional Access, Okta Adaptive MFA, CrowdStrike, Zscaler, Palo Alto. They own
  distribution, integrations, and enterprise trust. This is a **red ocean of incumbents**, not
  greenfield. The pivot only works with a *specific wedge*.
- **The wedge:** AI/agent-reasoned **consequence modeling over business and transaction
  *semantics*** — reasoning about intent, workflow meaning, privilege context — which the
  incumbents' rule/score engines do poorly. This fits the broader agentic work directly.
- **The hard boundary on AI (non-negotiable):** an LLM/agent must **not** sit in the real-time
  allow/block path — too slow (sub-second decisions), injectable (the attacker's actions *are*
  the model's input), and unauditable (regulators require deterministic, explainable decisions).
  AI belongs in **consequence modeling, offline policy synthesis, novel-workflow reasoning, and
  analyst augmentation**; the real-time decision is a fast, deterministic, auditable optimization
  over precomputed values. This boundary separates a defensible AI-security product from a
  liability.

Reframed ambition: not "a better detector" but "an **AI-native adaptive security decision layer**
whose differentiation is semantic consequence reasoning, sitting above deterministic real-time
enforcement." One-line: *innovate on how evidence is used, not on squeezing 2% from a biometric.*

---

## 4. Phased, gated plan

Critical path = DESIGN + real-systems (L2/L3/L4 + attestation/liveness). Biometric lane (L1
behavioral) runs **parallel and non-blocking**.

### Phase 0 — Consequence + Decision foundations (DESIGN; unblocked by data) — start now
- L2 value model `V_t = f(impact, irreversibility, privilege, recoverability)` for **one vertical**; enumerate its critical/irreversible actions.
- L3 decision engine as the constrained optimization (§2); cost model `λ₁, λ₂`; hard-constraint set.
- L4 action set + no-trust-inheritance (recompute risk at sensitive actions) + auditability/override.
- **Deliverable:** decision-engine spec + populated value model + cost model for one workflow.
- **Gate G0:** can you enumerate critical actions, assign 4-D consequence, and express the action-selection optimization for one real workflow? (Expected: yes.)

### Phase 1 — Attestation + context-bound liveness spike (RSYS; the differentiator) — parallel with Phase 0
- Integrate hardware attestation; three-state handling (PASS/FAIL/UNAVAILABLE).
- Prototype **one** context-bound liveness mechanism (nonce / UI-perturbation / hardware timestamp).
- **Deliverable:** working demo + measured replay-vs-live separation at real friction.
- **Gate G1 (highest-risk — de-risk first):** does context-binding distinguish a naive replay at acceptable friction? **No →** externally-grounded-trust thesis is in doubt; rethink before building. **Yes →** this is the moat.

### Phase 2 — MVP integration + operational evaluation
- Wire L2·L3·L4 + attestation/liveness hard gates, with `P` from a **deliberately mediocre** detector (proving weak-detector-is-OK).
- Evaluate against the operational kill criterion vs flat-policy and detector-only baselines.
- **Gate G2 (the product gate):** *at a fixed fraud-prevention target, does consequence-aware step-up reduce irreversible damage without unacceptable friction on legitimate critical actions?* **Yes →** a shippable damage-preventing product that does not depend on biometrics.

### Phase 3 — Friction-reduction / evidence lane (RDATA + cheap SYN) — parallel, non-blocking
- Instrumentation pilot (10–15 users): timestamp-sync + coupling-stability *feasibility*.
- USE Phase 1 signal-existence (frozen prereg): does user-specific coupling exist?
- Base behavioral EER on real data; E2 second-order kill (existing `kill_study` harness).
- **Gate G3 (drop-or-keep per component):** does the component reduce friction at equal security? **No → drop, don't relabel.** **Yes →** layer in as optimization.

### Phase 4 — Enhancements + hardening (after G2)
- L2 semantic reasoning via agent/LLM (offline/analyst — **not** the real-time path).
- Known-path precursor monitoring (secondary `γ` term) for the vertical's kill-chains.
- Dependence-aware fusion (E5) once real component outputs exist.
- Governance: value/cost-model drift + attacker-manipulation resistance; privacy/telemetry.
- Tier-C research (unknown-goal, joint-generative, full-compromise) tracked, never gating.

```
CRITICAL:  Phase 0 (DESIGN) ─┐
           Phase 1 (RSYS)  ──┼──► Phase 2 MVP ──[G2]──► ship ──► Phase 4
PARALLEL:  Phase 3 (RDATA/biometrics, drop-or-keep) ───────────────────┘ layer in if it helps
```

---

## 5. Effort allocation — and why risk ≠ effort

Rough 6–12 month allocation (aligned with the four-layer emphasis):

| % | Area | Layer |
|---|---|---|
| 40 | Decision engine + consequence modeling | L2 + L3 |
| 25 | Attestation, liveness, trustworthy evidence | L1 (grounded) |
| 20 | Orchestration + adaptive policy optimization | L4 (+ L3) |
| 10 | USE evaluation (does user-specific coupling exist?) | L1 (behavioral) |
| 5  | BCVF evaluation (does same-latent consistency add value?) | L1 (behavioral) |

**Effort ≠ risk-priority.** The attestation/liveness spike is *small effort* but the **highest-risk
gate (G1)** — the whole externally-grounded-trust thesis rests on it — so **sequence it first**,
in parallel with Phase 0, even though it is only ~25% of effort. Decision/consequence/orchestration
(60% combined) is the highest *leverage*; liveness is the highest *risk*. Fund by leverage,
sequence by risk.

---

## 6. Where BCVF and USE finally sit

- **BCVF:** one Layer-1 evidence producer, ~5% of the system. Not the architecture, product, moat,
  or detector. Keep if same-latent consistency beats a fair joint model (E1); remove otherwise.
- **USE:** a Layer-1 evidence producer, ~5–10%. Humanness (anti-automation) is the reliable job;
  identity is the Phase-1 gate. Keep the identity lane only if the residual exists.
- **SCC:** absorbed into L3/L4 as fusion + non-compensatory policy logic; no independent security
  claim.

The product's security does not wait on any of them.

---

## 7. Immediate next actions

1. **Draft the L2 consequence/value-model schema + L3 optimization spec** for one vertical (DESIGN) — highest leverage, no data needed. *The single most important next build.*
2. **Stand up the liveness/attestation spike (G1)** (RSYS) — highest-risk gate; parallelize from day one.
3. **E2 second-order kill** on the existing harness (SYN) — cheap loop-closure.
4. **Scope the behavioral data pilot** (RDATA) — parallel, non-blocking, for the friction lane only.

Central message: **build the consequence-gating + attestation MVP with an AI-reasoned
consequence layer and a deterministic real-time decision engine; treat behavioral biometrics as
a droppable friction-reduction input. Innovate on how evidence is used, not on the detector.**
