# Combined Cybersecurity Architecture — BCVF 2.0 + USE + SCC

**Status:** a *testable architecture spec*, not a validated product claim. Each component
carries an explicit status label (established / commodity-necessary / auxiliary-unproven /
unproven-pending-test). The next phase evaluates each part with **synthetic data, fair
baselines, and preregistered kill criteria** (§6). This document defines the combined design
and the corrected mathematics; it does **not** assert that every piece works.

Carries forward the conclusions of `BIOMETRIC_BCVF_SECURITY_REVIEW.md`,
`PROOF_PLAN_EVALUATION.md`, `kill_study/`, `BCVF_CONCEPT_DIRECTION.md`, and
`USE_CONTRIBUTION_MAP.md`.

---

## 0. Design principles (non-negotiable, from the prior analysis)

1. **Coherence ≠ truth.** Internal self-consistency is not ground truth. Consistency signals
   catch *incoherence*, not confident-and-wrong. Real security requires *external* evidence
   (attestation, liveness, verified anchors), not just agreement.
2. **Same-latent vs different-latent.** Disagreement between two estimators of the *same*
   quantity is a **consistency** signal (BCVF). Combining estimates of *different* quantities
   (identity vs liveness) is **fusion** (SCC) — never a subtraction.
3. **Non-compensatory gating.** Security-critical evidence (attestation, liveness) are
   **hard conjunctive gates outside the soft sum**. No amount of behavioral coherence buys
   back a failed gate. Attackers optimize the cheap-to-forge axes; a sum lets them.
4. **Dependence-aware fusion.** Evidence sources sharing inputs (USE and behavioral identity
   share the same streams) must not be counted as independent agreement.
5. **Classical backbone.** The primary detector is LLT-Kalman + CUSUM + a guarded adaptive
   template. This is the fair baseline everything else must augment, not replace.
6. **Liveness/attestation is the frontier.** The unsolved threats (coherent replay, joint
   generative mimicry, full compromise) are defeated only by hardware attestation +
   unpredictable-context binding, which this stack *feeds* but does not itself provide.
7. **Score ≠ action.** Detectors emit calibrated risk; a graduated policy chooses the action.
   No hard `ACCEPT iff C>θ` on a single scalar.
8. **Equalized evaluation.** Every added component must beat a baseline that already has the
   same information/capacity. Otherwise gains are capacity or more-data, not the component.

---

## 1. Notation

- `t` timestep; `m ∈ {1..M}` modality; `x_{m,t}` raw stream; `z_{m,t}` embedding.
- `c_t` context = (task, UI state, device class, sampling profile).
- `q_m(t) ∈ [0,1]` modality quality (presence, SNR, sampling validity).
- `μ_u(c_t), Σ_u(c_t)` context-conditioned enrolled-identity prototype; `μ_verified` the
  strong-auth anchor.

---

## 2. Layered architecture

```
L0  telemetry + timestamp sync + quality  q_m(t)
L1  BACKBONE (classical):  LLT-Kalman innovation + CUSUM  +  guarded adaptive template
L2a BCVF 2.0:  same-latent independent-observer consistency  (+ 2nd-order as auxiliary trigger)
L2b USE:       context-conditioned cross-modal coupling  (humanness + [unproven] identity)
L2c LIVENESS/ATTESTATION:  hard-gate evidence  (hardware, nonce-bound challenge)
L3  SCC:       non-compensatory, dependence-aware fusion + contradiction
L4  POLICY:    graduated risk actions + evidence scheduler (risk budget)
```

### L1 — Backbone detector (status: **established / fair baseline**)

Local-linear-trend Kalman per stream, state `[level, slope]`, `F=[[1,1],[0,1]]`, `H=[1,0]`:

```
innovation        y_t = z_t − H·(F·ŝ_{t-1})
innovation cov    S_t = H P_t Hᵀ + R
normalized surprise  ν_t = yᵀ S_t⁻¹ y            # calibrated, model-optimal
CUSUM accumulator  G_t = max(0, G_{t-1} + (√ν_t − κ))
```

Context-conditioned identity energy per modality:
```
E^id_{m,t} = (m_fast^{(m)} − μ_u^{(m)}(c_t))ᵀ Σ_{u,m}(c_t)⁻¹ (m_fast^{(m)} − μ_u^{(m)}(c_t))
```

Guarded adaptive template (equalizes poisoning resistance):
```
update m_slow  iff  ‖d‖ < τ_D  ∧  cum_disp < L  ∧  q > τ_q          # gate
project m_slow into ball(μ_verified, r_max)                          # anchor bound
require fresh MFA before r_max may increase                          # re-verified anchor
```
`G_t` is the primary anomaly signal; `E^id` and the guard are the identity/anti-poisoning core.

### L2a — BCVF 2.0 (status: **narrow principle; unproven-pending-test**)

Two **structurally independent** estimators of the **same** latent (identity) — e.g.
keystroke-identity `f₁(X)` vs mouse-identity `f₂(Y)`, or marginal-identity vs coupling-identity:

```
r^bcvf_t = ẑ^{(1)}_t − ẑ^{(2)}_t
q^bcvf_t = r^bcvf_tᵀ (Σ^{(1)}_t + Σ^{(2)}_t)⁻¹ r^bcvf_t          # χ²/FDI inter-estimator consistency
M^bcvf_t = η M^bcvf_{t-1} + ψ(q^bcvf_t − κ_b),   0 ≤ η < 1        # robust accumulation
```
This is the *sensor-fusion consistency test* (RAIM/FDI) applied to identity — sound, not novel.

**Auxiliary (status: auxiliary-unproven, likely null):** the second-order term
`a_t = d_t − 2d_{t-1} + d_{t-2}` is used **only** as a monotone-additive *evidence-scheduler
trigger* (§L4) — it may request more evidence, never defer a challenge or relax scrutiny. The
kill study found it null-to-negative as a detector; it is included here strictly as a cheap
trigger candidate to be tested against the KF surprise `√ν_t` and `G_t`.

### L2b — USE (status: **humanness = plausible; identity = unproven-pending-Phase-1**)

Per modality pair `(i,j)`, coupling `C_{ij}(t)` via a representation `g` chosen per pair
(point-process for event↔event, coherence for continuous↔continuous, CCA/CMI/contrastive
general — **not** phase-privileged). Coupling matrix `R_t = [C_{ij}(t)]`.

```
context residual   ρ_t = R_t − R_u(c_t)          # R_u fit train-only, marginal-residualized
identity energy    E^use-id_t = ‖ρ_t‖²_{W_R}      # USER-SPECIFIC coupling  (UNPROVEN)
humanness energy   E^use-hum_t = D(R_t ‖ generic-live-human coupling law)   (more reliable)
structural change  E^ΔR_t = ‖R_t − R_{t-1}‖²_{W_{ΔR}}
```
`E^use-hum` (Lane A, anti-automation) is the reliable contribution; `E^use-id` (Lane C,
identity) is exactly what the frozen USE Phase 1 tests via `C − A′`.

### L2c — Liveness / attestation (status: **commodity-necessary; the actual frontier defense**)

Hard-gate signals (binary or calibrated, **hardware-backed / nonce-bound**):
```
A_t = attestation_ok ∈ {0,1}      # device integrity, hardware root of trust
V_t = liveness_ok ∈ {0,1}         # response to unpredictable challenge / interface perturbation
```
These are **constraints, not summands** (Principle 3). They are the only defense against
coherent replay and joint generative mimicry; USE/BCVF/backbone all fail those without them.

### L3 — SCC (status: **commodity-necessary fusion/policy; not a differentiator**)

Soft, tradeable evidence vector (dependence-aware): identity `E^id`, USE `E^use-*`, BCVF
`M^bcvf`, backbone `G_t`, device-behavior and context-consistency.

**Dependence-aware, quality-weighted soft coherence** (whiten correlated sources; `Σ_e` is the
evidence covariance so shared-input signals are not double-counted):
```
w_m(t) = q_m(t) / (Σ_j q_j(t) + ε)
C^soft_t = wᵀ Σ_e⁻¹ e_t
           − λ_D · D_same-latent(t)      # BCVF disagreement among same-latent estimators
           − λ_X · D_cross-evidence(t)   # incompatible SOFT evidence (behavior vs context/session)
```

**Non-compensatory composition** — hard gates dominate the soft score:
```
R_t = R_max                                   if A_t = 0  OR  V_t = 0        # hard fail, non-negotiable
      g( C^soft_t, M^bcvf_t, G_t, q, c_t )     otherwise                      # soft risk
```
No `C^soft` value can lift `R_t` below `R_max` when a hard gate fails. This is the single most
important structural property; a compensatory (subtractive-penalty) form is exploitable.

### L4 — Graduated risk policy + evidence scheduler (status: **where value concentrates**)

```
a_t = π(R_t, M_t, budget, c_t):
  R_t < θ₁               → continue
  θ₁ ≤ R_t < θ₂          → increase observation
  θ₂ ≤ R_t < θ₃          → collect evidence / cheap passive probe   ← BCVF 2nd-order MAY trigger here (additive only)
  R_t ≥ θ₃               → step-up auth / restrict / terminate
```
With hysteresis (`θ_on > θ_off`), persistence (`m`-of-`K`), and a **risk/probe budget**. The
scheduler is where a weak-but-cheap trigger can help — *if* it beats the free triggers (§6).

---

## 3. The combined risk equation (compact)

```
Backbone   G_t   = CUSUM(√(yᵀS⁻¹y))                          # accumulation (workhorse)
Same-latent M^bcvf_t = leakyCUSUM( rᵀ(Σ¹+Σ²)⁻¹ r )           # inter-observer consistency
Coupling    E^use_t = ‖R_t − R_u(c_t)‖²                        # cross-modal (humanness ✓ / identity ?)
Soft fuse   C^soft_t = wᵀΣ_e⁻¹e_t − λ_D D_same − λ_X D_cross   # dependence-aware, quality-weighted
Hard gate   R_t = R_max if (¬A_t ∨ ¬V_t) else g(C^soft,M^bcvf,G_t,q,c_t)
Action      a_t = π(R_t, budget)                              # graduated, risk-budgeted
```

Reading: the backbone accumulates anomaly; BCVF adds same-latent consistency; USE adds
cross-modal coordination; SCC fuses the soft evidence (dependence-aware) and applies
attestation/liveness as **hard gates**; the policy acts on graduated risk. Attestation/liveness
can veto; nothing can veto them.

---

## 4. What each component is claimed to buy

| Component | Claimed contribution | Status |
|---|---|---|
| Backbone (Kalman+CUSUM+guards) | primary detection + poisoning resistance | **established** (fair baseline) |
| BCVF 2.0 same-latent consistency | flags disagreement between independent identity estimators | unproven-pending-test |
| BCVF 2nd-order (auxiliary) | cheap monotone trigger for evidence-gathering | auxiliary; likely null |
| USE humanness (Lane A) | anti-automation / independent-spoof detection | plausible (high conf) |
| USE identity (Lane C) | user-specific coupling beyond marginals | unproven (Phase 1) |
| Liveness / attestation | defeats coherent replay & generative mimicry | commodity-necessary (frontier) |
| SCC fusion + non-compensatory gates | session-level contradiction + safe combination | commodity-necessary |
| Graduated policy + scheduler | risk-budgeted action; friction control | where value concentrates |

---

## 5. What the combined system still cannot do

- **Full endpoint compromise** below the telemetry layer — all channels can be forged
  coherently; only hardware root-of-trust attestation helps, and only if uncompromised.
- **Coherent whole-session replay** and **joint generative mimicry** — defeated only by
  unpredictable-context binding in `V_t`; the statistical layers (backbone/BCVF/USE) all pass.
- **Stolen attestation credentials** — hard gate passes falsely; needs revocation + binding to
  a fresh nonce/interaction.
- **Slow poisoning vs legitimate drift** — bounded by the guard + re-verified anchor (friction
  cost), not eliminated; it is information-theoretically hard from behavior alone.

The combined architecture *raises attacker cost and covers more attack classes*; it does not
make spoofing impossible, and its hardest-threat coverage lives entirely in L2c.

---

## 6. Evaluation plan for the next phase (synthetic, component-wise, fair-baselined)

Each component is tested **against a baseline that already has its information**, with a
preregistered kill criterion. Reuse and extend the `kill_study/` harness (guarded observer,
Kalman, CUSUM, trajectory families, paired bootstrap, DET frontiers).

| # | Question | Fair baseline | Primary metric | Kill criterion |
|---|---|---|---|---|
| E1 | Does same-latent BCVF consistency add value? | independent-fusion of the two observers (no explicit disagreement term) | DET at fixed FAR on split-session / injected-swap attacks | BCVF must beat independent-fusion, paired-CI favorable |
| E2 | Does the 2nd-order term help as a scheduler trigger? | trigger on KF surprise `√ν_t` / CUSUM `G_t` at fixed probe budget | total cost + time-to-first-probe on graded onsets | must beat `√ν_t` trigger; else drop |
| E3 | Does USE coupling add identity info beyond marginals? | multimodal marginals `A′` + shuffled-coupling `A′_shuffle` | `C−A′` and `C−A′_shuffle`, same-device impostor | both CIs favorable ∧ ≥ Δ_min (frozen USE Phase 1) |
| E4 | Does non-compensatory SCC resist buy-back? | compensatory (subtractive-penalty) SCC | attack success under cheap-axis maximization w/ failed hard gate | non-compensatory must block what compensatory admits |
| E5 | Does dependence-aware fusion beat naive w-sum? | naive quality-weighted sum (independent assumption) | FAR under single-stream compromise that fakes multi-channel agreement | dependence-aware must not be fooled by correlated inputs |
| E6 | Does the full stack beat the backbone alone? | backbone (Kalman+CUSUM+guards) | DET frontier + damage-weighted detection on the full attack battery | stack must add coverage on ≥1 attack class w/o friction regression |

Attack battery (synthetic): abrupt takeover, slow-linear, smooth low-curvature,
detector-aware, gate-aware poisoning, independent-modality spoof, coherent replay, misaligned
replay, same-task same-device live impostor, full-coherent (all channels agree falsely),
missing-modality, timestamp jitter.

**Decision discipline (from the prior studies):**
- Preregister metrics, baselines, and kill criteria before running; verdict is mechanical.
- Require **practical** effect size (`Δ_min`), not just CI-excludes-zero (the n=1024 lesson).
- Any component that fails its E-test is dropped from the combined solution, not relabeled.
- L2c (liveness/attestation) is a *control*, tested by whether it blocks the full-coherent and
  replay attacks the statistical layers pass — not by a discrimination metric.

**Expected-going-in priors (to be confirmed or falsified):** backbone carries detection;
liveness/attestation carries the frontier; SCC's value is the non-compensatory policy, not the
formula; USE-humanness likely helps, USE-identity uncertain; BCVF same-latent uncertain and
2nd-order likely null. The next phase exists to make those priors earn or lose their place.
