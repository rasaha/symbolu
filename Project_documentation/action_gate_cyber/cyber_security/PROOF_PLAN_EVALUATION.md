# BCVF-Bio — Proof Plan Evaluation & Corrected Validation Design

**Status:** Consolidated technical evaluation of the proposed validation roadmap.
**Companion to:** `BIOMETRIC_BCVF_SECURITY_REVIEW.md` (design review).
**Scope:** Whether the proposed proofs, if completed, would actually establish the
central claim — and what the corrected experiment must be.

This document consolidates three review passes: the original design review, a critique
of the proof plan, and a third-party (ChatGPT) round that accepted the critique and
extended it. It records where all three converge, and the additional corrections that
survive the third round.

---

## 1. Bottom line

The proof plan is an honest **engineering-validation** roadmap and a good friction study.
As a **security proof** it was originally scoped to the friendly threat. The third round
corrected this by reframing BCVF-Bio as a *composite guarded-adaptation architecture*
rather than "the second derivative detects slow takeover." That reframing is correct — but
it has a consequence its author lists as merely one of three outcomes when it is actually
the **prior**:

> Once security is attributed to cumulative-change detection, verified-anchor bounds,
> gated adaptation, and liveness — all conventional — the only original component,
> the second-order operator `Δ²d`, has been demoted to friction reduction. The entire
> program then reduces to **one 2-D frontier comparison** that can be run cheaply *before*
> any longitudinal data collection.

If that frontier gap is small, there is no differentiated invention. Everything else in the
roadmap is downstream of that single question and should not be funded until it is answered.

---

## 2. The meta-flaw and how the reframing fixes (and doesn't fix) it

### 2.1 Original flaw: the proof standard tested the case the operator wins

The original central claim — "detects **abrupt or accelerating** divergence earlier while
producing fewer challenges during gradual drift" — restricts itself to the input class the
second-order operator was built for. `Δ²d ≈ 0` for any affine `d_t = a + b·t`, so a slow
linear-ramp attacker is invisible to `E_A` **by construction**. The plan's "decisive
experiment" made this worse by defining *genuine drift = gradual* and *takeover = abrupt* —
the discriminating axis of the operator itself. That is tautological: it proves an
acceleration detector can tell abrupt from gradual, not that the system is secure.

### 2.2 The correct reframing (accepted)

A slow linear takeover is invisible to `Δ²d`, but **not necessarily invisible to the full
system**. For `d_t = a + b·t`, `Δ²d = 0` yet the following can still grow:

```
‖d_t‖ ,   Σ_{k=t-H}^{t} ‖Δd_k‖ ,   ‖m_b(t) − m_verified‖ ,   attacker-directed baseline drift
```

So the honest thesis is **not** "second-order divergence detects slow takeover." It is:

> Second-order divergence reduces false reactions to ordinary gradual drift, while
> **separate** cumulative-displacement, anchor-distance, and change-detection mechanisms
> protect against slow takeover and poisoning.

BCVF-Bio is therefore a *composite guarded-adaptation architecture*, not a claim that the
second derivative is a complete takeover detector.

### 2.3 What the reframing quietly concedes (correction that survives round 3)

The four guards the composite thesis leans on are all conventional and none is the
second-order term:

| Guard in the composite thesis | Conventional equivalent |
|---|---|
| Cumulative displacement limit | CUSUM |
| Verified-anchor bound | Distance-to-enrollment (standard) |
| Poisoning-aware adaptation | Gated template update (adaptive-biometrics self-update literature) |
| Liveness / context evidence | Orthogonal existing technology |

Consequently the "partial positive" outcome (*second-order improves friction; security comes
entirely from conventional controls*) is **the prior**, not an equiprobable third of the
outcome space. The reframing has already half-argued for it. The live question shrinks to
§3.

---

## 3. The decisive reduction — run this before longitudinal collection

If poisoning resistance comes from the gate, a **fair** benchmark equips *every* baseline
with the same anchor + gate + deadband + hysteresis. Do that and poisoning resistance is
equalized **by construction**, so "beats CUSUM on poisoning" is only achievable by denying
the baseline the gate — an unfair baseline. Once every method shares the guards, the only
axis the second-order operator can win on is a single 2-D frontier:

> **False challenges per genuine-user-hour vs detection of abrupt/naturalistic transitions —
> first-order-with-guards vs second-order-with-guards, identical guards.**

This is cheap (synthetic + public data), ablation-friendly, and decisive. If the frontier
gap is negligible, the invention does not exist and no further stage is justified.

### 3.1 The attribution ablation (sharpest single test)

The claimed friction benefit is bundled from three separable sources:

- (a) the second-order operator's blindness to linear drift,
- (b) the deadband (`kσ`),
- (c) hysteresis / persistence (`m`-of-`K` windows).

All three suppress false challenges under gradual drift. To credit the **second-order term**
(the novelty), hold (b) and (c) **identical** and toggle only the operator order:

```
Control  : first-order  observer + SAME deadband + SAME hysteresis + SAME anchor + SAME gate
Treatment: second-order observer + SAME deadband + SAME hysteresis + SAME anchor + SAME gate
```

If Control matches Treatment on friction, the deadband was doing the work and the invention
contributes nothing even to friction. This is the make-or-break test and must be run first.

---

## 4. Corrected hypotheses (two claims, preregistered)

### 4.1 Friction claim (may succeed)

At a fixed detection rate for abrupt and naturally occurring impostor transitions, adding
second-order divergence reduces false challenges during legitimate longitudinal drift
relative to static and first-order adaptive baselines **carrying identical guards**.

### 4.2 Security claim (must be allowed to fail)

When slow takeover trajectories are matched to legitimate drift, the complete guarded system
does not perform worse than tuned change-point baselines and limits attacker-directed
template movement.

### 4.3 Preregistered falsification (kill condition)

> Under slow / approximately linear takeover trajectories generated by a **detector-aware
> optimal attacker**, the complete BCVF-Bio system fails differentiation if it does not
> improve at least one of {takeover detection, attacker-directed template displacement `D_∥`,
> damage-weighted detection latency} relative to the strongest tuned first-order / change-point
> baseline **carrying identical guards**.

This prevents a clean abrupt-takeover result from rescuing a failed adaptive-threat result.

---

## 5. Required baselines (all carrying identical guards unless the ablation removes one)

1. Static threshold
2. Unrestricted EWMA adaptation
3. Guarded first-order fast/slow observer  ← attribution control (§3.1)
4. CUSUM on `d_t`
5. CUSUM on identity mismatch `E_I(t)`
6. BOCPD or ADWIN
7. Full BCVF without second-order term
8. Full BCVF without cumulative-displacement bound
9. Full BCVF without verified anchor
10. Complete BCVF-Bio

CUSUM is the critical competitor because it accumulates small persistent deviations with
negligible instantaneous acceleration — exactly the slow-drift regime `Δ²d` is blind to:

```
S_t = max(0, S_{t-1} + r_t − κ)
```

If CUSUM matches the complete system with less complexity, the differentiation claim
collapses.

---

## 6. The attacker model — do not settle for accel-matched

Matching only `‖Δ²d_attack‖ ≈ ‖Δ²d_legit‖` matches **one moment**. A detector-aware attacker
optimizes against the **whole composite score**, matching cumulative-displacement rate and
anchor trajectory too. An accel-matched-but-otherwise-sloppy attacker is a subtler strawman:
CUSUM catches it and BCVF "wins" for the wrong reason.

**Requirement:** generate Condition-B trajectories with a detector-aware optimal attacker
(projected-gradient or RL trajectory that minimizes detection probability across the *full*
detector subject to reaching the target behavior state). Report all detection rates as an
**upper bound under a named, bounded attacker model**, never as unqualified numbers.

Additional realism note: in most collections "impostors" are other enrolled participants
typing *naturally* — a stranger being themselves, the weakest attacker. Detection rate on
naive impostors is a **ceiling**, not a result.

---

## 7. Metrics

### 7.1 Poisoning — direction, not magnitude

Total baseline movement is insufficient. With
`v_attack = (m_attacker − m_verified) / ‖m_attacker − m_verified‖`:

```
D_∥ = ⟨ m_b(T) − m_b(0), v_attack ⟩            # attacker-directed displacement (primary)
D_⊥ = ‖ (m_b(T) − m_b(0)) − D_∥ · v_attack ‖    # harmless orthogonal drift
```

`D_∥` is the security-relevant quantity: modest movement *toward* the attacker is damaging;
large orthogonal drift is not. Also measure **acceptance-margin erosion** — whether poisoning
actually makes the attacker more acceptable:

```
M_erosion = score(m_attacker, m_b(T)) − score(m_attacker, m_b(0))
```

`M_erosion` measures the outcome; `D_∥` measures the mechanism. Report both.

### 7.2 Damage-weighted latency — a min-max, not an integral

```
𝒟 = Σ_{τ=t_takeover}^{t_response} w_action(τ)      # e.g. read=low, records=med, payment=high, transfer=critical
```

Caveat: `𝒟` depends on the **attacker's** action policy (a smart attacker front-loads the
critical action into window 1, inflating `𝒟` regardless of detection speed). `𝒟` is a
property of the detector × attacker-policy *pair*, not of the detector. Therefore the attacker
action-model must be **preregistered and fixed**, and `𝒟` reported as **worst-case over
attacker policy** (min-max), not a value you simply compute.

### 7.3 Operating point — DET curve, not a single threshold

The proposed primary endpoint ("false challenges subject to ≥95% detection before a damage
threshold") is **undefined if no method — CUSUM included — reaches the 95% point** against an
optimal slow attacker. Replace it with the full **DET curve** (detection-rate vs
false-challenge-rate) and compare by area or at multiple preregistered operating points.

### 7.4 Primary and secondary endpoints

- **Primary:** false challenges per genuine-user-hour along the DET frontier, first-order-with-
  guards vs second-order-with-guards (the §3 reduction).
- **Secondary:** `D_∥`; `M_erosion`; poisoning success rate; median & 95th-pct detection
  latency; FAR/FRR across thresholds (NIST-aligned, reported as curves not one accuracy
  number); challenge burden; baseline recovery time; calibration error; performance by attack
  type.

---

## 8. Unresolved architectural tension — anchor vs adaptation

Adding **verified-anchor bounds** (`‖m_b − m_verified‖`) reintroduces the problem the slow
adaptive observer existed to solve. A *fixed* enrollment anchor fights legitimate multi-week
drift: over time `‖m_b − m_verified‖` grows for benign reasons, so the anchor bound must either
false-challenge the drifting legitimate user or loosen enough to admit slow poisoning. This
cannot be escaped with a static anchor — it needs **periodically re-verified anchors** (step-up
/ strong auth), which reintroduce friction. The anchor bound and the adaptive slow observer are
in direct opposition; the composite reframing relocates the friction-vs-security tradeoff into
the anchor-radius hyperparameter rather than dissolving it. This must be treated as an open
design problem, not a solved guard.

---

## 9. Study sizing

Power on **events, not participants**. 30 users × 1 takeover = 30 attack events, inadequate
near a 95% detection target. Pilot design:

- 30–50 users; 10–20 genuine longitudinal sessions each; multiple takeover types per user;
- **≥ 200–400 total attack events**;
- attacker identities **held out** from threshold tuning;
- bootstrap CIs **clustered by participant and attacker source** (repeated events are not
  independent).

Counterbalance session order and device-condition assignment; account for novelty / Hawthorne
effects.

---

## 10. Corrected sequencing (red-team moved forward)

1. Algebraic / unit-test verification (invariance — already covered by
   `bcvf_autonomous` `test_linear_drift_zero_cost`; a sanity check, not a proof of value).
2. **The §3 reduction + §3.1 attribution ablation** (synthetic + public data, guards equalized).
   Cheap. Decides whether to continue.
3. Synthetic adversarial trajectories including a **detector-aware** slow attacker (§6).
4. CUSUM / BOCPD comparison with guards equalized (§5).
5. Small **live red-team** pilot — surfaces telemetry needs (liveness, attestation,
   attack-direction) *before* the large collection is designed.
6. Finalize telemetry + longitudinal protocol; then the larger longitudinal study.
7. FSCS **only** after the security path is established — and it must gate a *cost* path only,
   never the security detector (see design review §3.6).

Moving the red-team ahead of the large collection avoids gathering an expensive dataset that
later proves to lack the liveness / attestation / attack-direction channels the security case
needs.

---

## 11. The three honest outcomes (with corrected priors)

- **Strong positive** — the complete system beats CUSUM/BOCPD **with guards equalized** on the
  friction frontier and on `D_∥`/`M_erosion`. *Note:* poisoning resistance is equalized by the
  shared gate, so a "poisoning win" over an ungated CUSUM does not count.
- **Partial positive (the prior)** — second-order improves friction, but security comes
  entirely from conventional change-point and anchor controls.
- **Negative** — tuned conventional baselines with the same guards match the system; BCVF is an
  elegant repackaging.

The corrected program is worth running precisely because all three remain possible — but the
§3 reduction reaches the decision point for a fraction of the cost of the full roadmap.

---

## 12. Actionable core (what to build first)

1. Implement the **guarded-baseline harness**: first-order and second-order observers behind an
   *identical* deadband + hysteresis + anchor + gate, plus CUSUM(`d_t`), CUSUM(`E_I`),
   BOCPD/ADWIN.
2. Run the **§3.1 attribution ablation** and the **§3 2-D frontier** on synthetic +
   public keystroke/mouse data. This is the go/no-go gate.
3. If it passes, write the **preregistration**: two claims (§4.1–4.2), the falsification target
   (§4.3), the detector-aware attacker (§6), `D_∥`/`M_erosion`/min-max `𝒟` metrics (§7),
   DET-curve endpoint (§7.3), event-based power (§9).
4. Only then collect longitudinal data.
