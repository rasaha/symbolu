# Roadmap — Adaptive Security Orchestration (consequence-first)

**Status:** the forward plan after the full BCVF → USE → SCC → consequence-gating analysis.
Capstone to `GAP_REGISTER.md`, `COMBINED_ARCHITECTURE_BCVF2_USE_SCC.md`,
`BCVF_CONCEPT_DIRECTION.md`, `USE_CONTRIBUTION_MAP.md`, and `kill_study/`.

**Rev. 2:** added Phase −1 threat modeling (so `V` is derived, not invented); split liveness into
commodity attestation (G1a, low-risk floor) vs novel context-bound liveness (G1b, parallel
research enhancement — not a ship blocker); renamed Phase 3 to the pluggable "Evidence
Innovation Lane"; added the safety-monotone (escalate-only) constraint on real-time agentic
orchestration with full reasoning kept offline; kept mission→intent→goal modeling secondary and
backstopped; noted the differentiation ceiling depends on the AI semantic layer, not on any
evidence source.

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

Critical path = threat modeling → DESIGN (consequence + decision) + commodity trust. The novel
liveness research and the biometric lane run **parallel and non-blocking**.

### Phase −1 — Threat modeling (DESIGN; must precede consequence modeling)
Without the attack graph, the value model `V` is arbitrary. Derive it, don't invent it:
```
assets → threats → attacker objectives → attack paths → critical actions → consequence model
```
- **Deliverable:** for one vertical, the asset/threat/objective map and the concrete attack
  paths (e.g. `reset MFA → change email → add beneficiary → transfer`).
- **Dual use:** the attack **paths** become both the source of "which actions are critical" (→ L2)
  and the kill-chains for goal-progress monitoring (→ the secondary `γ` term).
- **Gate G−1:** is there an enumerated attack graph with named critical actions? (Prereq for G0.)

### Phase 0 — Consequence + Decision foundations (DESIGN; unblocked by data) — start now
- L2 value model `V_t = f(impact, irreversibility, privilege, recoverability)` **derived from the
  Phase −1 attack graph** for one vertical.
- L3 decision engine as the constrained optimization (§2); cost model `λ₁, λ₂`; hard-constraint set.
- L4 action set + no-trust-inheritance (recompute risk at sensitive actions) + auditability/override.
- **Deliverable:** decision-engine spec + populated value model + cost model for one workflow.
- **Gate G0:** can you enumerate critical actions, assign 4-D consequence, and express the action-selection optimization for one real workflow?

### Phase 1A — Commodity trust (RSYS; low research risk) — parallel with Phase 0
- Integrate off-the-shelf attestation: Play Integrity / App Attest / Windows TPM / secure enclave / device binding; three-state handling (PASS/FAIL/UNAVAILABLE).
- **Deliverable:** working attestation gate + explicit MFA step-up as the liveness *floor*.
- **Gate G1a (engineering, not research):** is attestation deployable on the target endpoints, and what is the real-world UNAVAILABLE rate? This de-risks most of the externally-grounded-trust thesis immediately — it already exists commercially.

### Phase 1B — Novel context-bound liveness (RSYS **research**; the actual gamble) — parallel
- Prototype **one** novel mechanism: unpredictable UI perturbation / dynamic interaction proof / human-response timing / hardware timing fingerprint.
- **Deliverable:** measured replay-vs-live separation at real friction, vs the MFA floor.
- **Gate G1b (highest research risk — but an enhancement over a commodity floor):** does context-binding separate replay at *lower friction than explicit MFA*? **No →** ship on the commodity floor (attestation + MFA); novel liveness is deferred, **not** blocking. **Yes →** load-bearing specifically against the **relay / real-time-MITM / coherent-generation** threat that static MFA cannot resist (an unpredictable proof is hard to relay live). This is where the moat, if any, actually is.

### Phase 2 — MVP integration + operational evaluation
- Wire L2·L3·L4 + attestation/MFA hard gates, with `P` from a **deliberately mediocre** detector (proving weak-detector-is-OK).
- Evaluate against the operational kill criterion vs flat-policy and detector-only baselines.
- **Gate G2 (the product gate):** *at a fixed fraud-prevention target, does consequence-aware step-up reduce irreversible damage without unacceptable friction on legitimate critical actions?* **Yes →** a shippable damage-preventing product that does not depend on biometrics or on novel liveness.

### Phase 3 — Evidence Innovation Lane (RDATA + cheap SYN) — parallel, non-blocking
A **pluggable lane** where *any* evidence source competes on the same incremental-value test —
BCVF, USE, graph embeddings, foundation-model reasoning, new sensors, future models. Not tied
to today's hypotheses.
- Instrumentation pilot (10–15 users): timestamp-sync + coupling-stability *feasibility*.
- USE Phase 1 signal-existence (frozen prereg); base behavioral EER; E2 second-order kill.
- **Gate G3 (drop-or-keep, uniform per candidate):** does the source reduce friction / add coverage at equal security, ≥ Δ_min? **No → drop, don't relabel.** **Yes →** layer in.

### Phase 4 — Enhancements + hardening (after G2)
- **Agentic orchestration (safety-monotone):** an agent in the **real-time** path may only
  *escalate* (add scrutiny, require stronger proof) — **never relax/allow**. Full reasoning
  (allow decisions, novel-workflow analysis, policy synthesis) runs **offline / analyst-facing**,
  not in the sub-second decision. Connects L4 to the existing Agentic Framework (governance,
  budget allocation, safety orchestration).
- **Mission→intent→goal→action modeling** as an *enrichment* of L2/L3 and analyst explanation —
  kept **secondary and backstopped** (intent inference is attacker-manipulable and blind to
  novel paths; it never load-bears the real-time block decision).
- Dependence-aware fusion (E5) once real component outputs exist.
- Governance: value/cost-model drift + attacker-manipulation resistance; privacy/telemetry.
- Tier-C research (unknown-goal, joint-generative, full-compromise) tracked, never gating.

```
CRITICAL:  Phase −1 (threat model) ─► Phase 0 (DESIGN) ─┐
           Phase 1A commodity trust  ─────────────────── ┼─► Phase 2 MVP ──[G2]──► ship ──► Phase 4
PARALLEL:  Phase 1B novel liveness (enhancement, G1b) ───┘   (moat vs relay/generation if it passes)
PARALLEL:  Phase 3 Evidence Innovation Lane (drop-or-keep) ──┘ layer in if it helps
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

**Effort ≠ risk-priority, and the risk is now split.** Attestation (**G1a**) is commodity
engineering — do it early to establish the trust *floor*; it de-risks most of the
externally-grounded-trust thesis because it already exists commercially. **Novel liveness
(G1b)** is the highest *research* risk — but it is an **enhancement over that floor**, not a
product blocker (the MVP can ship on attestation + MFA). So it runs in parallel and does not
gate the ship. Decision/consequence/orchestration (60% combined) is the highest *leverage*.
**Fund by leverage (L2/L3/L4), sequence commodity trust early, treat novel liveness as a
parallel research bet whose payoff is the relay/generation-resistant moat.** The real
make-or-break for the product is **G2**, not liveness.

**Differentiation ceiling (the 7/10 reality).** Most components — RBA, attestation,
orchestration, step-up — are established; inventing them is not a moat. The one lever that
raises differentiation above table-stakes is executing the **AI-reasoned semantic
consequence/intent layer** well *and safely* (offline reasoning + escalate-only real-time).
Differentiation ≈ the quality of that layer, not the novelty of any evidence source.

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

1. **Threat-model one vertical (Phase −1)** — asset/threat/objective map + concrete attack paths + named critical actions. *Prerequisite that makes `V` non-arbitrary.*
2. **Draft the L2 consequence/value-model schema + L3 optimization spec** derived from that attack graph (DESIGN) — highest leverage, no data needed. *The single most important next build.*
3. **Integrate commodity attestation (G1a)** (RSYS) — establishes the trust floor early; low research risk.
4. **Stand up the novel-liveness spike (G1b)** (RSYS, research) — parallel, non-blocking; the potential relay/generation-resistant moat.
5. **E2 second-order kill** on the existing harness (SYN) — cheap loop-closure; enters the Evidence Innovation Lane.
6. **Scope the behavioral data pilot** (RDATA) — parallel, non-blocking, Evidence Innovation Lane only.

Central message: **threat-model first, then build the consequence-gating + commodity-attestation
MVP with an AI-reasoned (offline) consequence/intent layer and a deterministic, escalate-only
real-time decision engine. Treat behavioral biometrics — and even novel liveness — as
droppable/parallel enhancements. Innovate on how evidence is used, not on the detector.**
