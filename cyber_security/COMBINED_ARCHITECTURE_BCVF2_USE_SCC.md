# Combined Cybersecurity Architecture — BCVF 2.0 + USE + SCC

**Status:** a *testable architecture spec*, not a validated product claim. Each component
carries an explicit status label (established / commodity-necessary / auxiliary-unproven /
unproven-pending-test). The next phase evaluates each part with **synthetic data, fair
baselines, and preregistered kill criteria** (§6). This document defines the combined design
and the corrected mathematics; it does **not** assert that every piece works.

Carries forward the conclusions of `BIOMETRIC_BCVF_SECURITY_REVIEW.md`,
`PROOF_PLAN_EVALUATION.md`, `kill_study/`, `BCVF_CONCEPT_DIRECTION.md`, and
`USE_CONTRIBUTION_MAP.md`.

**Rev. 2 (pre-freeze corrections incorporated):** SCC soft fusion replaced by a single
calibrated discriminative risk `g_θ` (no double-counted subtractive penalties); three-state
attestation/liveness gates (`PASS`/`FAIL`/`UNAVAILABLE`) so absent evidence escalates instead
of auto-rejecting; USE-humanness relabeled two-tier (reliable vs crude, unproven vs
coordinated); E1 baseline strengthened to a joint model; E4 reframed as a security-vs-friction
trade-off; E6 tightened with `Δ_min`/no-regression/cost bounds; the two product paths marked
separable in evaluation (§4.5); component-wise execution order and expected end-state added.

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

### L2b — USE (status: **humanness = tiered; identity = unproven-pending-Phase-1**)

Per modality pair `(i,j)`, coupling `C_{ij}(t)` via a representation `g` chosen per pair
(point-process for event↔event, coherence for continuous↔continuous, CCA/CMI/contrastive
general — **not** phase-privileged). Coupling matrix `R_t = [C_{ij}(t)]`.

```
context residual   ρ_t = R_t − R_u(c_t)          # R_u fit train-only, marginal-residualized
identity energy    E^use-id_t = ‖ρ_t‖²_{W_R}      # USER-SPECIFIC coupling  (UNPROVEN)
humanness energy   E^use-hum_t = D(R_t ‖ generic-live-human coupling law)
structural change  E^ΔR_t = ‖R_t − R_{t-1}‖²_{W_{ΔR}}
```
`E^use-hum` (Lane A) has a **two-tier** status, not a blanket "reliable":

- **Reliable against independent / crude generation** — independent per-modality production
  genuinely breaks joint timing, so stitched, scripted, and time-shifted streams are caught
  near-structurally.
- **Unproven against coordinated adversaries** — a joint multimodal generator, synchronized
  replay, or malware driving the normal UI stack can preserve coupling; USE-humanness is
  *not* validated here and must be tested against graded negatives (Phase 1 levels 1–5).

`E^use-id` (Lane C, identity) is exactly what the frozen USE Phase 1 tests via `C − A′`.

### L2c — Liveness / attestation (status: **commodity-necessary; the actual frontier defense**)

Hard-gate signals are **three-state**, not binary — an explicit failure is different from
absent evidence (a binary gate would force max-risk on inactivity or a missing sensor):
```
A_t ∈ {PASS, FAIL, UNAVAILABLE}      # attestation: hardware root of trust
V_t ∈ {PASS, FAIL, NOT_OBSERVED}     # liveness: response to unpredictable challenge / nonce
```
- **FAIL** = explicit cryptographic/liveness failure → hard veto (non-negotiable, §L3).
- **UNAVAILABLE / NOT_OBSERVED** = evidence absent → *force an evidence-gathering action or
  step-up and degrade trust* — **not** an automatic max-risk reject.
- **PASS** → allow the soft policy to proceed.

These are **constraints, not summands** (Principle 3). Explicit-FAIL is the only defense
against coherent replay and joint generative mimicry; USE/BCVF/backbone all fail those without
it.

### L3 — SCC (status: **commodity-necessary fusion/policy; not a differentiator**)

Soft, tradeable evidence vector `e_t` (dependence-aware): identity `E^id`, USE `E^use-*`,
BCVF `M^bcvf`, backbone `G_t`, device-behavior and context-consistency.

**Soft risk = a calibrated discriminative model, not a hand-weighted sum.** A raw
`wᵀΣ_e⁻¹e_t` is neither a calibrated risk nor of fixed sign/scale, and manually subtracting a
`D_same-latent` penalty *double-counts* the BCVF disagreement that is already a feature in
`e_t`. Use a calibrated log-likelihood-ratio (or a regularized, calibrated discriminative
function), with **each signal entering `e_t` exactly once** and dependence handled by the
model, not by manual penalties:
```
R^soft_t = g_θ(e_t, c_t),   e.g.   ℓ_t = log [ p(e_t | attack, c_t) / p(e_t | legit, c_t) ]
linear fallback:  R^soft_t = b(c_t) + βᵀ e_t     # regularized; b, β calibrated on held-out data
```
`M^bcvf` (same-latent disagreement) and the USE residuals are **columns of `e_t`** — the model
learns their weight and correlation; there is no separate `λ_D`/`λ_X` subtraction.

**Non-compensatory composition** — explicit hard-FAIL dominates; absent evidence escalates:
```
R_t = R_max                       if A_t = FAIL  OR  V_t = FAIL            # explicit failure: hard veto
      escalate(step-up / probe)   if A_t = UNAVAILABLE OR V_t = NOT_OBSERVED   # absent evidence: force evidence, degrade — NOT auto-max
      R^soft_t = g_θ(e_t, c_t)    otherwise (both PASS)                     # calibrated soft risk
```
No soft score can lift `R_t` below `R_max` on an explicit hard-FAIL. This non-compensatory
property is the single most important structural decision; a compensatory (weighted-sum or
subtractive-penalty) form lets an attacker maximize cheap axes to offset a decisive failure.

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
Same-latent M^bcvf_t = leakyCUSUM( rᵀ(Σ¹+Σ²)⁻¹ r )           # inter-observer consistency  → a column of e_t
Coupling    E^use_t = ‖R_t − R_u(c_t)‖²                        # cross-modal (humanness tiered / identity ?) → column of e_t
Soft risk   R^soft_t = g_θ(e_t, c_t)                          # CALIBRATED discriminative risk; each signal once; dependence in the model
Composition R_t = R_max            if A_t=FAIL ∨ V_t=FAIL
                = escalate(...)     if A_t=UNAVAIL ∨ V_t=NOT_OBSERVED
                = R^soft_t          otherwise (both PASS)
Action      a_t = π(R_t, budget)                              # graduated, risk-budgeted
```

Reading: the backbone accumulates anomaly; BCVF adds same-latent consistency; USE adds
cross-modal coordination; all soft signals enter a **single calibrated risk model** `g_θ`
(no manual double-penalty); attestation/liveness act as **three-state hard gates** where only
an explicit FAIL is a non-negotiable veto and absent evidence escalates rather than
auto-rejects. Nothing soft can veto an explicit hard-FAIL.

---

## 4. What each component is claimed to buy

| Component | Claimed contribution | Defensible status |
|---|---|---|
| Backbone (Kalman+CUSUM) | primary detection | established *method*; application performance unvalidated |
| Guarded template + anchor | poisoning resistance | established *defense*; residual slow-poisoning risk |
| BCVF 2.0 same-latent consistency | disagreement between independent identity estimators | pending incremental test (vs a joint model) |
| BCVF 2nd-order (auxiliary) | cheap monotone scheduler trigger | pending cheap kill test; low prior |
| USE humanness (Lane A) | anti-automation / independent-spoof detection | plausible, unvalidated (reliable vs crude, unproven vs coordinated) |
| USE identity (Lane C) | user-specific coupling beyond marginals | Phase 1 gate |
| Attestation | device integrity | necessary where deployable; **not sufficient** |
| Active liveness | defeats coherent replay & generative mimicry | **central unvalidated product mechanism** |
| SCC fusion + gates | session-level contradiction + safe combination | policy/fusion layer, **no independent security claim** |
| Graduated policy + scheduler | risk-budgeted action; friction control | likely product differentiator; needs decision-theoretic validation |

## 4.5 Two separable product paths (do not conflate in evaluation)

The stack contains two distinct paths that must remain **separable in implementation and
evaluation**, or a positive result from one launders a null in the other:

- **Identity-security path:** backbone (Kalman/CUSUM) + identity models + guarded template +
  verified anchor. Handles ordinary takeover and poisoning resistance.
- **Integrity/liveness path:** attestation + nonce-bound interaction + USE-humanness + policy
  scheduling. Handles replay, automation, and synthetic interaction.

If evaluated only as a monolith, a strong attestation result can make the whole "combined
architecture" look successful while BCVF and USE-identity contribute nothing. Attribute per
path, and per component within each path.

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

| # | Question | Fair baseline (must already hold the information) | Primary metric | Kill criterion |
|---|---|---|---|---|
| E1 | Does explicit same-latent disagreement add value? | a **joint discriminative model** over `(ẑ¹,ẑ²,Σ¹,Σ²)` — allowed to learn the relationship itself | DET at fixed FAR on split-session / injected-swap attacks | `joint+BCVF-residual − joint-alone` paired-CI favorable ∧ ≥ Δ_min (not vs a forbidden-to-learn baseline) |
| E2 | Does the 2nd-order term help as a scheduler trigger? | trigger on KF surprise `√ν_t` / CUSUM `G_t` at fixed probe budget | total cost + time-to-first-probe on graded onsets | must beat `√ν_t` trigger; else drop |
| E3 | Does USE coupling add identity info beyond marginals? | multimodal marginals `A′` + shuffled-coupling `A′_shuffle` | `C−A′` and `C−A′_shuffle`, same-device impostor | both CIs favorable ∧ ≥ Δ_min (frozen USE Phase 1) |
| E4 | Non-compensatory gate: security-vs-friction trade-off | compensatory (weighted-sum) fusion, **matched** legit-availability & missing/unavailable-attestation rates | attack acceptance **and** step-up burden jointly | reduce attack acceptance without an unacceptable step-up increase (a hard gate that rejects-everyone-on-missing-evidence fails this) |
| E5 | Does dependence-aware fusion beat naive w-sum? | naive quality-weighted sum (independence assumption) | FAR under single-stream compromise that fakes multi-channel agreement | dependence-aware must not be fooled by correlated inputs (**run on real component outputs; synthetic covariance alone is insufficient**) |
| E6 | Does the full stack beat the backbone alone? | backbone (Kalman+CUSUM+guards) | DET frontier + damage-weighted detection on the full attack battery | `Δdamage ≤ −Δ_min` **and** no material regression on existing classes **and** `Δcost ≤ B_max` **and** attack class frequent/severe enough to justify deployment |

> E1 note: the two independent same-latent observers can be **keystroke-identity vs
> mouse-identity** (no USE required) or **marginal-identity vs coupling-identity** (requires
> E3 to pass first). The former lets E1 run independently of USE.

> E4 note: this is a *trade-off* test, not the tautology "does `A=FAIL ⇒ R_max` block a
> FAIL" (true by construction). The point is whether non-compensatory gating buys real attack
> reduction at acceptable friction once `UNAVAILABLE`/`NOT_OBSERVED` states exist.

Attack battery (synthetic): abrupt takeover, slow-linear, smooth low-curvature,
detector-aware, gate-aware poisoning, independent-modality spoof, coherent replay, misaligned
replay, same-task same-device live impostor, full-coherent (all channels agree falsely),
missing-modality, timestamp jitter.

**Execution order (do NOT run E1–E6 simultaneously — it invites attribution problems):**
1. **E3 / USE Phase 1** — does user-specific coupling exist? (gates the identity lane)
2. **Liveness/attestation feasibility** — does unpredictable-context binding actually separate
   replay / joint generation at acceptable friction? (the frontier mechanism)
3. **E2** — second-order scheduler kill test (cheap, pure-synthetic, independently removable;
   can run first if convenient — it needs nothing else)
4. **E1** — same-latent disagreement vs a joint model (via keystroke-vs-mouse identity now, or
   marginal-vs-coupling identity if E3 passes)
5. **E5** — dependence-aware fusion, once real component outputs exist
6. **E4** — policy hard-gate security-vs-friction trade-off
7. **E6** — full-stack, **only after each component has independently survived**

**Decision discipline (from the prior studies):**
- Preregister metrics, baselines, kill criteria before running; verdict is mechanical.
- Require **practical** effect size (`Δ_min`), not just CI-excludes-zero (the n=1024 lesson).
- Any component that fails its E-test is **dropped, not relabeled**.
- Evaluate the two product paths (§4.5) **separately** so attestation cannot mask BCVF/USE nulls.
- L2c (liveness/attestation) is a *control*, tested by whether it blocks the full-coherent and
  replay attacks the statistical layers pass — not by a discrimination metric.

**Expected end-state (to be confirmed or falsified).** The most likely surviving system is:
```
Kalman+CUSUM backbone + verified anchor + active liveness/attestation + risk-budgeted policy
```
with USE retained only if coupling survives Phase 1; BCVF retained only if explicit same-latent
disagreement beats a fair joint model; the second-order term likely removed; SCC retained as
implementation-level fusion/policy, not a standalone invention. If so, the **differentiated
technical thesis is not BCVF, USE, or SCC individually** — it is *risk-budgeted orchestration
of hardware-backed and context-bound liveness evidence under continuous session risk.* The next
phase exists to make each component earn or lose its place against that end-state.
