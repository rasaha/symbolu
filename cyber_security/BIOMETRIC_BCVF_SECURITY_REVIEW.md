# Biometric BCVF — Security Evaluation

**Status:** Independent technical review
**Subject:** Continuous-authentication BCVF (fast/slow behavioral observers, second-order
divergence) proposed as a security application of the autonomy BCVF.
**Reviewer scope:** Mathematical soundness + security posture of the reformulated design.

---

## 0. Provenance check (what this review is grounded in)

The reformulation cites two prior-work claims. Both are accurate against the repository:

- **Second-order invariance.** `symbolu_robotics/bcvf_autonomous/DESIGN.md` implements the
  operator `a_ij(k) = [e(k+1) − 2·e(k) + e(k−1)] / dt²` (Def 3) with a
  `test_linear_drift_zero_cost` unit test (§2.4.1). Constant and linear-drift disagreement
  produce zero cost; only acceleration produces a positive signal ("Lemma 1 invariance").
- **Consumer layer (EMA centering + deadband).** `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` records
  the validated config `T=0.05, β=400, EMA α=0.05, deadband k=2σ, non-anchor pairing`,
  validated at N=21 seeds *in a simulator* (sign test p=0.0072).

So the reformulation faithfully extends existing work. This review takes that faithfulness
as given and evaluates whether the extension is *secure*.

---

## 1. Verdict

The reformulation is a genuine improvement over the original scalar Lagrangian, and its
mathematics are sound. But it is a **control / signal-processing framework wrapped around an
unvalidated, spoofable, low-SNR sensor with no stated threat model.** The parts it gets right
are not the parts that decide whether the system is secure. The parts that decide security are
the two terms it develops least — `E_I` and `E_Q` — and its headline feature, the second-order
invariance, is a double-edged property that quietly *creates* the most important attack.

Take the reformulation over the scalar original every time. Do **not** ship it as an
authenticator, and do not add more math until the threat model, the spoofing defense, and an
EER measurement exist.

---

## 2. What the reformulation gets right (affirmed)

1. **The critique of the scalar Lagrangian is correct.** Collapsing identity match,
   disagreement, and rate-of-disagreement into a single quadratic conflates a benign
   *common-mode decline* (both `s_f` and `s_b` fall together — fatigue, device change) with a
   genuine anomaly. Splitting into identity / disagreement / acceleration / quality energies is
   the right decomposition.

2. **The Lyapunov correction is correct and non-trivial:**
   - A cost function is not a Lyapunov function until it is attached to a state-update system.
   - The honest stability target is **input-to-state stability (ISS) with a bounded tube**, not
     convergence to zero — human behavior never reaches a fixed point.
   - `ΔV > 0 ⇒ intruder` is too strong; benign events (keyboard→trackpad switch, injury, stress,
     posture change, sensor dropout) also exit the modeled regime.

3. **The poisoning correction is correct.** An L2 penalty against `s_b = 1` does not stop the
   slow filter from absorbing attacker behavior. You need an explicit adaptation gate that
   *freezes* the baseline `m_b` under suspicion. The gate structure `g_t = 1[‖d‖ < τ_D ∧
   ‖a‖ < τ_A ∧ q > τ_q]` is the right shape.

4. **Graduated response + hysteresis + persistence** (continue / observe / challenge / restrict,
   with `θ_off < θ_on` and "m of last K windows") is better than a single hard lockout threshold.

These are real and worth keeping.

---

## 3. The gaps that decide security (where the risk actually lives)

### 3.1 The second-order invariance is also the primary vulnerability — HEADLINE

`Δ²d = 0` for **any** affine sequence `d_t = a + b·t`. That is precisely what makes `E_A`
robust to benign linear drift — **and precisely what makes it blind to a malicious linear
ramp.** A patient adversary who interpolates *linearly* from victim-behavior toward
attacker-behavior produces `Δ²d ≈ 0` at every step and is invisible to the celebrated detector
**by construction.**

You cannot make one operator simultaneously robust-to-benign-linear and
sensitive-to-malicious-linear. Consequences:

- The security burden falls onto `E_I` (absolute Mahalanobis distance to the enrolled
  prototype) — the calibration-based, no-invariance, false-positive-prone term the reformulation
  leans on least.
- The adaptation gate is conditioned on `‖a_t‖` being *small*. A slow linear-ramp attack keeps
  `g_t = 1`, keeps the baseline adapting, and **reproduces the exact template-poisoning the gate
  was meant to prevent.**

**The invariance that is the differentiator in autonomy is a documented blind spot in
adversarial biometrics.** This must be stated explicitly in any external-facing material.

### 3.2 There is no threat model

The entire design implicitly assumes an *unaware* takeover (someone sits at an unlocked
machine). It is silent on:

- **Response observability.** Each step-up challenge leaks that `R_t` crossed `θ₂`; an adaptive
  attacker binary-searches the threshold.
- **Replay** of captured victim telemetry.
- **Generative spoofing.** Behavioral biometrics are *sampleable*. A script that draws keystroke
  flight/dwell times from the victim's own distribution matches `µ_u` by construction and defeats
  `E_I`, `E_D`, and `E_A` at once.

`E_Q` (the "sensor-quality / spoofing" term) is doing all the real security work while being
completely unspecified. Right now it is a placeholder for the hard 80% of the problem.

### 3.3 It is an anomaly detector, not authentication

Real-world EER for continuous keystroke/mouse dynamics is ~5–15% in the lab and worse in the
wild. No amount of ISS / hysteresis / fusion changes the sensor SNR. This is elegant control
theory on a weak signal. Acceptable as *one risk factor*; not acceptable as an authenticator.

### 3.4 The autonomy evidence base does not transfer

The validated config came from N=21 seeds **in a simulator**. Human behavior cannot be simulated
at that fidelity, and no validation path is proposed. Meanwhile the parameter count exploded:

`λ_I, λ_D, λ_A, λ_P, λ_Q`; per-band `α_f, α_b, τ_D, τ_A`; `Σ_u, Σ_f, Σ_b`; deadband `k`;
fusion `w_I…w_Q`; modality weights `ω_m(t)`; action thresholds `θ₁, θ₂, θ₃`; hysteresis
`θ_on, θ_off`; persistence `(K, m)`; and FSCS's `γ_b, δ_b, ρ_b, η_b, τ_{m,b}` per modality-band.

Dozens-to-hundreds of hyperparameters, each a calibration burden and an attack surface, with no
dataset behind them.

### 3.5 The ISS bound is partly decorative

`‖e_t‖ ≤ c·ρᵗ·‖e₀‖ + γ(w̄)` requires a *known, stable* error-transition matrix `A_e`
(`A_eᵀ P A_e − P = −Q`, spectral radius < 1). But `d_t = m_f − m_b` is driven by the human input
`z_t`; there is no controller closing the loop, so `A_e` is not a plant you designed — it is
whatever the human (or attacker) produces. The bounded-tube claim is therefore a *modeling
assumption about benign behavior* (empirically checkable), not a proven guarantee. The boxed
algebra implies more rigor than exists.

### 3.6 FSCS on the security path is a category error

FSCS originated as an LLM-inference **cost** optimization: reuse cached summaries when coherence
is high. Placed in front of a security detector it hands the attacker a lever — keep input
coherent/steady to suppress full feature extraction exactly when scrutiny should be highest.
"Suspected boundary → force full compute" only relocates the problem to the boundary detector,
which is the thing under attack. FSCS may gate a *cost* path; the security detector must run at
full fidelity always, or on a schedule the attacker cannot predict.

### 3.7 Enrollment / prototype modeling

`E_I` uses a single Gaussian prototype `(µ_u, Σ_u)`. Human behavior is multimodal (mouse vs
trackpad are distinct clusters, not one Gaussian) and non-stationary across days/devices/posture.
A single Mahalanobis energy is mis-specified. Needs a mixture / per-context prototype, plus a
defined enrollment budget and a measured false-reject rate during the first week.

---

## 4. What is required before more math

1. **Write the threat model first.** Aware vs unaware attacker; same-hardware vs remote; replay;
   generative spoofing; whether the attacker can observe responses. Everything downstream depends
   on this and it is currently absent.
2. **Make `E_Q` concrete.** It is the term actually holding the line against spoofing/replay —
   that means liveness, hardware/input attestation, and challenge-response, not a scalar. Treat
   behavioral biometrics as one weak factor in that stack, not as the authenticator.
3. **Measure EER on real data.** Control theory cannot rescue a ~10%-EER sensor. Until there is a
   dataset and a measured operating point, the framework is untestable.
4. **Close the linear-ramp hole explicitly.** The second-order term must be backstopped by a
   strong absolute-identity term and by baseline-freeze logic that does *not* itself depend on
   `Δ²d` being large. Consider a mixture / per-context prototype for `µ_u`.

---

## 5. One-line summary

The reformulation makes the right corrections, but it mistakes **mathematical structure** for
**security**. The second-order invariance is an asset in autonomy and a liability in adversarial
biometrics, and the two undeveloped terms (`E_I`, `E_Q`) are where the entire security claim
actually rests.
