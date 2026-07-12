# BCVF — Concept Direction (post-kill-study)

**Status:** converged conceptual position for the behavioral-security line, after the
adversarial synthetic kill study and the BCVF-2.0 review. This document records what was
refuted, what the architecture actually is, the narrow principle worth keeping under the
"BCVF" label, and the staged program. It supersedes any framing that treats second-order
divergence as the invention.

Companion artifacts: `BIOMETRIC_BCVF_SECURITY_REVIEW.md`, `PROOF_PLAN_EVALUATION.md`,
`kill_study/` (preregistration + results), and the USE Phase 1 plan.

---

## 1. What was refuted

The kill study (`kill_study/RESULTS_RECORD.md`) tested second-order BCVF as a primary
takeover detector against a **fair, guards-equalized** LLT-Kalman + CUSUM baseline (same
identity + disagreement channels; only the temporal channel differed). Held-out result on
1,024 paired adaptive-attack events: the second-order term produced **no practically
meaningful security gain** (the one significant axis was a 0.13%-relative damage-weighted
difference) and **significantly regressed** adaptive-attack detection and legitimate-drift
friction. Net: **second-order divergence is null-to-negative as a primary detector**,
consistent with the `Var(Δ²d) = 6σ²` finite-difference noise-amplification argument.

**Do not** re-advance "second-order BCVF detects takeover while tolerating drift." It has
been fairly tested and did not hold.

## 2. What the architecture actually converged to

"BCVF 2.0" (context-conditioned residuals, covariance normalization, robust loss, adaptive
weights, cumulative memory, directional monitoring, policy separation) is a real improvement
over the original fixed-target quadratic — but each upgrade maps onto a classical component:

```
expected-state residual + covariance normalization  →  Kalman normalized innovation
cumulative memory  M_t = ηM_{t-1}+max(0,L_t−κ)       →  leaky/forgetting CUSUM
directional monitoring  ⟨d_t, v_k⟩                    →  attacker-direction / persistent-drift (guard-supplied)
score → estimator → policy                            →  detector-agnostic orchestration
```

So the operational architecture is, plainly:

```
state-space prediction  +  normalized innovation  +  CUSUM-like memory  +  guarded policy
```

That is the same classical hybrid that beat the distinctive second-order formulation. Build
it — but recognize that "BCVF" here is mostly a legacy label on standard machinery, and it
does not, by itself, constitute a novelty or a moat.

## 3. The one principle worth keeping under the "BCVF" name

Define BCVF **structurally and narrowly**, not by any fixed Lagrangian:

> **BCVF = uncertainty-normalized, accumulated consistency between two _structurally
> independent_ estimators of the _same_ latent property, exposed to a bounded policy.**

```
ẑ¹_t = f₁(X_t),  ẑ²_t = f₂(Y_t)          # f₁, f₂ meaningfully independent; SAME target quantity
r_t  = ẑ¹_t − ẑ²_t
q_t  = r_tᵀ (Σ¹_t + Σ²_t)⁻¹ r_t          # joint-uncertainty-normalized disagreement
M_t  = η M_{t-1} + ψ(q_t − κ)            # robust accumulation
a_t  = π(q_t, M_t, c_t)                   # bounded policy
```

Two hard requirements distinguish this from generic machinery:

- **Independence:** `f₁` and `f₂` must differ structurally — different modalities, models,
  information sources, or inductive biases. Two EWMA rates of one stream are **not**
  independent observers; their difference is a band-pass/trend filter and carries no
  consistency information a single filter lacks.
- **Same latent property:** both estimators must target the **same** quantity, so `r_t` is a
  genuine *disagreement about one thing*. Comparing estimates of *different* properties
  (identity vs liveness, semantic vs process) is **evidence fusion**, not consistency
  verification — governed by inverse-variance combination, not a disagreement residual.
  Coherent examples: keystroke-identity vs mouse-identity; **marginal-model identity vs
  coupling-model identity** (the USE Phase 1 arms).

### Honest novelty status

Even in this strong form, the mechanism is **not new**. Uncertainty-normalized disagreement
between two independent estimators of the same quantity, accumulated over time, is the
classic **inter-estimator consistency test from sensor fusion / fault detection and isolation**
(χ²/Mahalanobis residual gating — e.g. GPS-IMU integrity monitoring / RAIM, multi-sensor
FDI) followed by CUSUM. The defensible contribution is **applying** inter-observer
consistency-gating to continuous authentication plus the accumulate-and-policy wrapper — an
engineering-and-organizing contribution, not a mathematical one. Do not market it as new math.

## 4. What does NOT count as BCVF (falsifiability guard)

To keep the term meaningful, the following are implementation components, not the BCVF core.
If "BCVF" is stretched to cover them, it becomes an unfalsifiable umbrella for any
observer-based control system:

- two EWMA speeds on the same stream;
- the second finite difference as the defining mechanism;
- fixed target 1; fixed λ weights;
- a generic Kalman innovation;
- a generic CUSUM;
- a generic policy engine;
- disagreement between estimators of **different** latent properties (that is fusion).

## 5. Staged program (unchanged; freeze stands)

```
instrumentation feasibility pilot
   → USE Phase 1: multimodal marginals  vs  context-conditioned coupling   [FROZEN]
      → (only if Phase 1 passes) Phase 2: independent-observer disagreement, narrowly isolated
```

- **Phase 1 tests USE, not BCVF.** No BCVF enters. If USE's user-specific coupling residual
  does not exist (see the frozen Phase 1 plan), there is no reason to test BCVF-on-USE.
- **Phase 2, only on `USER_SPECIFIC_COUPLING_SUPPORTED`,** must isolate the *one* retained
  BCVF principle, not a sprawling "BCVF 2.0" stack (which is indistinguishable from the
  baseline). The valid, equalized contrast is:

  > **classical hybrid with the two observers used independently (fused)**
  > vs
  > **same system + explicit uncertainty-normalized inter-observer disagreement**

  This isolates whether *consistency-gating between independent same-latent observers* adds
  anything beyond treating those observers as independent fusion inputs. Prior from the kill
  study and from §3: uncertain — plausibly small — and it must be allowed to return a null.

## 6. What none of this solves — the real frontier

Reshuffling the detector layer does not move the security frontier. The unsolved problems
remain **liveness / replay / AI-generated mimicry** (needs attestation and unpredictable-
context binding, not consistency math) and the **anchor-vs-legitimate-drift impossibility**
(needs external re-verification / MFA). BCVF — in any form — touches none of these. The
differentiated value, if the company pursues one, lives in the liveness/attestation +
risk-budgeted orchestration layer, with behavioral biometrics as one commoditized input.

## 7. Bottom line

- Second-order BCVF as a primary detector: **refuted, do not revive.**
- "BCVF 2.0": **good engineering, but it is the classical hybrid under a legacy label.**
- Retain "BCVF" only as the **narrow principle** of same-latent independent-observer
  consistency-gating — sound and useful, but a known statistical tool, not novel mechanism.
- Keep Phase 1 frozen; define Phase 2 as the single equalized disagreement-vs-fusion contrast.
- The security frontier is liveness/attestation and orchestration, not the detector.
