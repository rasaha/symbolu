# B1.3 Raw-Varṇa Feature-Model Options (pivotal gate)

## 1. Scope

Assesses whether the raw varṇa sequence can produce a feature vector **without dictionary lookup or
circularity**. Development-only; DEVELOPMENT_FREEZE; the feasibility probe here is **NOT evidence** (per
`../b1_2_mapping_fidelity/FREEZE_POLICY.md`). No B1.1/B1.2 modification, no rescue, no positive/utility/
ontology/Sanskrit/semantic-truth claim, Track B BLOCKED. **Structure, not validated meaning.**

## 2. The core problem

To map a varṇa (a sound unit) into an **external semantic** feature space (WordNet hypernyms), one needs a
model `M: varṇa (+pole+position) → feature contribution`. Where can `M` come from **non-circularly**?

- **A. Fixed varṇa→external-feature table** — no such pre-existing, principled table exists. Hand-authoring it
  is arbitrary/circular. → not available.
- **B. Rule-based varṇa operator model** (existing polarity/role rules) — still needs a varṇa→feature bridge;
  the only one Symbol-U supplies is the **bridge glosses**, which failed B1.2 (generic). → forbidden as the
  primary V source.
- **C. Compositional varṇa-sequence kernel** — order-sensitive composition is possible, but still needs a base
  varṇa→feature map (same gap as A/B).
- **D. Development-only learned calibration** — fit `M` on a **training** word split, freeze it, test on a
  **disjoint held-out** split. This is the *only* non-circular route to an empirical `M`. (Tuning `M` to the
  70 target G answers and calling it evidence is explicitly forbidden.)

**Every route ultimately depends on there being a real varṇa→meaning regularity to encode or learn.** If none
exists, A–D are all dead: a fixed table would be arbitrary, and a learned model would fit noise and fail
out-of-sample.

## 3. Development feasibility probe (NOT evidence)

Before adjudicating the learned-`M` route, we tested the necessary precondition directly: **is there any
correlation between raw varṇa-sequence distance and semantic (G) distance?** (No model, no judge; morphological
/substring pairs excluded; 70-word pool.)

| metric | value | reading |
|---|---|---|
| pairs tested | 2,412 | |
| Spearman ρ (varṇa dist vs semantic dist) | **0.0079** | ≈ 0 |
| Pearson r | 0.0056 | ≈ 0 |
| permutation-ρ baseline | [−0.0275, −0.0248, −0.0257, +0.0285, +0.0058] | real ρ sits **inside** the noise band |
| varṇa-nearest-neighbor semantic lift | **0.0105** | sound-nearest word is **not** meaning-nearer than average |

**Finding: no detectable raw-varṇa→meaning signal.** Words with similar varṇa sequences are no more similar in
meaning than random pairs, and the varṇa-nearest neighbor carries essentially no semantic lift.

## 4. Answers to the required questions

- **Is there an existing pre-G varṇa→feature rule?** No — only bridge glosses (failed) and poles; neither maps
  to an external semantic space non-circularly.
- **Can one be specified without circularity?** Only via learned `M` on a disjoint train/test split (route D).
- **Can it represent order (V_scrambled ≠ V_real)?** Yes in principle (order-sensitive kernel) — but moot: §3
  shows no base signal exists to compose.
- **Can it support V_deranged / V_removed?** Yes structurally — also moot without signal.
- **Is it likely to avoid the generic-resonance failure?** **No.** With ρ≈0 and nn-lift≈0, a learned `M` has
  nothing to generalize; it would reproduce the B1.2 generic/word-non-specific outcome (V_deranged≈V_real).

## 5. Decision

```
DECISION: RAW_VARNA_FEATURE_MODEL_NOT_FEASIBLE_STOP_NOW
```

The raw-varṇa Layer-3 model requires a varṇa→meaning regularity to encode. The development probe shows that
regularity is **absent** by the two most natural tests (distance correlation ρ≈0 within permutation noise;
nearest-neighbor semantic lift ≈0). With no signal to learn, no **non-circular** model (fixed table A/B/C, or
learned `M` route D) can produce a word-specific prediction; the only way to make V match G would be to tune
`M` to the answers, which is forbidden and would not generalize. `FEASIBLE_TO_SPEC` and
`HIGH_RISK_NEEDS_ADJUDICATION` are therefore not chosen.

**Humility caveat:** this probe tests the *natural* varṇa↔meaning signal (global distance correlation +
nearest-neighbor lift), not literally every conceivable nonlinear model. But the burden of showing a signal
exists is clearly **unmet**, and the finding is **convergent** with every prior result — B1
`RANDOM_OR_SCRAMBLED_MATCHES`, B1.1 same, Track G `RANDOM_POLARITY_EXPLAINS`, and B1.2
`V_deranged≈V_real`. Independent methods keep finding the same absence.

## 6. Consequence for the workplan

This is a **hard STOP** at the pivotal gate. Gates 6–8 (target/control pool, audits, prereg readiness)
presuppose a feasible V model and are **not** executed. The autonomous sequence halts here and recommends
closure.

## 7. Status

```
document:        B1.3 raw-varṇa feature-model OPTIONS (development; feasibility probe only, NOT evidence)
decision:        RAW_VARNA_FEATURE_MODEL_NOT_FEASIBLE_STOP_NOW
probe:           ρ(varṇa,meaning)=0.008 (perm band [-0.027,+0.029]); nn semantic lift=0.010 — no signal
routes A/B/C:    no non-circular fixed varṇa→feature map exists
route D (learned): nothing to learn (ρ≈0) → would fit noise, fail out-of-sample
B1.1 verdict:    UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:         BLOCKED
EVIDENCE_FREEZE: NONE (development finding, not evidence)
next gate:       VARNA_LINE_CLOSURE_MEMO
```

**Structure, not validated meaning.** The raw-varṇa Layer-3 path has no underlying varṇa→meaning signal to
model non-circularly; the workplan halts at Gate 5 and recommends closure. B1.1's verdict is unchanged, Track
B remains BLOCKED, and nothing here is evidence — it is a convergent development finding.
