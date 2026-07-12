# Gap Register & Revised Roadmap

**Status:** working register of what is unknown/unbuilt, ranked by whether it blocks a
damage-preventing product. Supersedes the implicit "detector-first" ordering. Companion to
`COMBINED_ARCHITECTURE_BCVF2_USE_SCC.md`, `BCVF_CONCEPT_DIRECTION.md`, and
`USE_CONTRIBUTION_MAP.md`.

---

## 0. Strategic conclusion (explicit, up front)

> **The product does not depend on solving behavioral biometrics.** Consequence-aware
> orchestration and externally-grounded trust controls (attestation, context-bound liveness)
> carry the **primary** security responsibility. Behavioral signals (BCVF/USE/anomaly) reduce
> friction and add supplementary evidence — they are **not** the load-bearing security.

```
Security MVP        =  consequence gating  +  attestation/liveness  +  risk-based orchestration
BCVF/USE/biometrics =  friction-reduction  +  supplementary evidence   (non-blocking)
```

Why this holds: at a **critical or irreversible** action the impact term dominates, so the
system can **always** step up regardless of a weak `P(attack)`. Consequence-gating makes a
weak detector acceptable, which decouples "prevent damage" from "identify the user."

Honest caveat (keep it calibrated): this is **risk-adaptive access control** — mature, not
novel; the win is execution and the specific evidence sources. And the consequence/goal models
below are the *new* hard, brittle, attacker-manipulable problem. This roadmap is "correct and
buildable," not "a moat by itself."

---

## 1. The decision model (corrected — not a scalar action value)

The consequence of an action is **multi-dimensional**, not one number:

```
V_t = f( impact, irreversibility, privilege, recoverability )
```

Expected loss weights probability by consequence **and** by how hard it is to recover:

```
L_t = P(attack | E_{1:t}) · V_t · ρ_t          # ρ_t ↑ as recovery gets harder / action irreversible
```

Separate **current-action** risk from **future-path** risk; keep the path term **secondary**:

```
R_t = P(H_A | E_{1:t}) · [ V(a_t, c_t)  +  γ · Σ_k P(G_k | a_{1:t}) · V(G_k) ]
                          └ current action ┘   └ future-path (small γ) ┘
```

The goal-progress term is **secondary by design**: it is much harder to estimate reliably and
is blind to unknown attack paths. It may *advance* interception on known kill-chains; it must
never be load-bearing, and the general anomaly detector remains the backstop for the unknown.

---

## 2. Gap register — three tiers

Legend for **closure instrument**: `DESIGN` = enterprise/app-context modeling (NOT behavioral
biometrics); `RSYS` = real-systems engineering spike; `RDATA` = real behavioral data;
`SYN` = synthetic study. Legend for **status**: mature / buildable / pending / frontier.

### Tier A — Critical-path capabilities (MVP; a failure here = no product)

| Capability | Gap to close | Closure | Status | Notes |
|---|---|---|---|---|
| **Consequence/value model `V_t`** | build the multi-dim `f(impact, irreversibility, privilege, recoverability)` over actions × context × resources | DESIGN | buildable | living artifact; stale `V` = blind spots; attacker-manipulable → govern it |
| **Irreversibility / recoverability classification `ρ_t`** | map each action to reversibility + clawback window | DESIGN | buildable | often more decisive than raw impact |
| **No-trust-inheritance policy** | recompute risk (require stronger evidence) whenever a session approaches a sensitive action | DESIGN | buildable | closes "behave normally in recon, cash in at reward" |
| **Hardware/device attestation** | integrate root-of-trust; define UNAVAILABLE handling | RSYS | mature-where-deployable | necessary, **not sufficient**; deployability varies by endpoint |
| **Nonce / context-bound liveness** | prototype binding one channel to unpredictable current context; measure separation of replay/generation at real friction | RSYS | pending (**central mechanism**) | the actual frontier defense; G5 |
| **Graduated response & step-up orchestration** | policy engine acting on `L_t` with hysteresis, persistence, risk budget | DESIGN | buildable | the likely product differentiator |
| **Auditability & policy override** | log evidence → decision; human override; explainable step-up | DESIGN | buildable | required for enterprise trust + incident review |

### Tier B — Important but non-blocking enhancements (friction reduction / supplementary)

| Capability | Gap | Closure | Status |
|---|---|---|---|
| Behavioral anomaly score (Kalman+CUSUM backbone) | validate on real data | RDATA | established method, app-perf unvalidated; **backstop for unknown paths** |
| USE cross-modal coupling | does user-specific coupling exist? | RDATA | pending (frozen Phase 1) |
| BCVF same-latent consistency | beat a fair joint model? | RDATA/SYN | pending |
| Goal-progress inference (**known** attack paths) | model known kill-chains | DESIGN | buildable but bounded to modeled paths |
| Adaptive evidence scheduling | cheap trigger beats KF-surprise? | SYN | pending (low prior for 2nd-order) |

### Tier C — Research-frontier / high-risk (do NOT gate the product on these)

| Item | Why hard | Closure | Status |
|---|---|---|---|
| Unknown-goal inference | open-world; sparse labels | RDATA/research | frontier |
| Joint generative mimicry detection | attacker matches joint law | RDATA/research | frontier (needs liveness, not detection) |
| Full endpoint compromise | all channels forgeable coherently | RSYS/research | frontier (needs uncompromised root-of-trust) |
| Reliable user-specific coupling | may not exist after context conditioning | RDATA | Phase 1 gate |
| Slow poisoning vs legitimate drift | information-theoretically hard from behavior alone | RDATA/design | bounded by anchor + re-verification, not solved |
| Calibration under sparse real attack labels | few labeled takeovers | RDATA | frontier; amplified by `R=P·V` at high `V` |

---

## 3. Priority ranking (execution order)

1. **Critical-action gating** — always verify critical actions; the core of "weak detector is OK."
2. **Irreversibility-aware policy** — `ρ_t`; gate on expected *irreversible* loss, not just value.
3. **Attestation & active liveness** — the externally-grounded trust the whole stack rests on.
4. **No trust inheritance** — recompute risk at sensitive actions; no coasting on prior normalcy.
5. **Known-path precursor monitoring** — secondary `γ`-weighted term; earlier interception on modeled kill-chains.
6. **Behavioral friction optimization** — BCVF/USE/anomaly reduce step-up on legitimate high-stakes actions.
7. **Novel-goal inference** — research; never on the critical path.

Items 1–4 are the MVP and are **largely unblocked by the behavioral-data gap** (they are
DESIGN/RSYS, not RDATA). Items 5–7 are enhancements/research.

---

## 4. Closure-instrument summary (where effort actually goes)

- **DESIGN (enterprise/app modeling, not biometrics)** — consequence model, irreversibility map,
  no-trust policy, orchestration, auditability. **This is the MVP critical path and is not
  blocked by the biometric real-data gap.**
- **RSYS (real-systems spikes)** — attestation integration, context-bound liveness feasibility.
  The differentiator; must be prototyped, not simulated.
- **RDATA (real behavioral data)** — base EER, user-specific coupling (Phase 1), calibration.
  Gates only the **friction** lane (Tier B), not the product.
- **SYN (synthetic)** — 2nd-order scheduler kill (E2), policy-logic prototyping, dependence-aware
  fusion (needs real outputs later). Cheap loop-closure; not on the critical path.

The earlier "build the E1–E6 harness" impulse maps almost entirely to SYN/RDATA — i.e. the
**friction** lane — and should not precede the DESIGN/RSYS critical path.

---

## 5. MVP kill criterion (operational, not ROC)

> **At a fixed fraud-prevention target, does consequence-aware step-up reduce irreversible
> damage without creating an unacceptable challenge burden on legitimate critical actions?**

- Primary outcome: **irreversible-damage-prevented vs step-up burden on legitimate critical
  actions** — reported as a frontier, not a single point.
- Baseline: flat-policy step-up (no consequence weighting) and no-op (detector-only).
- This replaces "the biometric detector has a slightly better ROC" as the success bar. A better
  detector ROC is neither necessary nor sufficient for the MVP to succeed.

---

## 6. What each tier's failure means

- **Tier A fails → no product.** These are non-negotiable; the security responsibility lives here.
- **Tier B fails → product still works, with more friction.** Drop the failed component (do not
  relabel); the detector lane is an optimization, not a dependency.
- **Tier C fails → expected.** These are backstopped by Tier A (consequence gating + always-verify
  critical/irreversible) and by the general anomaly detector; the product is designed to remain
  safe when they are unsolved.

---

## 7. Immediate next steps (concrete)

1. **Consequence/value model + irreversibility map** (DESIGN) — the highest-leverage build; MVP core.
2. **Attestation + context-bound liveness feasibility spike** (RSYS) — prove the differentiator separates naive replay at acceptable friction.
3. **No-trust-inheritance + graduated `L_t` orchestration prototype** (DESIGN) — the policy engine on expected irreversible loss.
4. **E2 second-order scheduler kill** (SYN, existing `kill_study` harness) — cheap loop-closure; retire the last 2nd-order claim.
5. **Scope the behavioral data pilot** (RDATA, parallel/non-blocking) — for the *friction* lane (USE Phase 1, base EER); not on the MVP critical path.

The register's central message, restated: **build the consequence-gating + attestation MVP
first; the behavioral detector is a friction-reduction enhancement layered on top, and the
product's security does not wait on solving behavioral biometrics.**
