# Bhava / Ontology Supervised Probe — Plan (PRE-REGISTERED)

> **Scope.** Generation-quality research track only. This probe asks one question and does **not**
> modify the CG wrapper generation path, training behaviour, or any governance/trust code, and does
> **not** add mid-layer injection. It is a *read-only diagnostic*: extract features from a frozen
> model + trained Active-CG head, then test with lightweight supervised probes whether the
> Bhava/ontology features carry generation-quality signal **beyond generic hidden states**.

## 0. The one question

The CG ablation tests whether the wrapper *changes generation usefully* (likely
`STATIC_OFFSET_NO_CG_DYNAMIC`, because generation consumes `ΔBhava ≈ 0`). This probe asks the
**prior** question, on the Bhava **value** (not its delta):

> Does the Bhava / 32D ontology representation predict generation-quality outcomes, and does it
> add anything **over generic hidden states**?

If a probe on raw hidden states already predicts the label and Bhava adds nothing, the ontology is
not load-bearing for generation — no injection redesign will help.

## 1. Features probed

Extracted per labeled example from a frozen backbone + the trained Active-CG head:

| Group | Features |
|-------|----------|
| **A. Bhava value** | `bhava[0:12]` (softmax), `dominant_bhava` (argmax id, one-hot), `bhava_entropy`, raw pre-softmax `bhava_logits` if exposed |
| **B. Ontology / CG state** | full 32D `state`; `kosha[12:17]`, `vritti[17:22]`, `guna[22:28]`, `reserved[28:32]` slices; token-ontology projection if accessible |
| **C. Delta** | `ΔBhava`, `‖ΔBhava‖`, `intent_phase` vector |
| **D. Generic hidden baselines (REQUIRED)** | mean-pooled final hidden state; last-token final hidden state; (optional) selected mid-layer hidden states if accessible |

Group D is mandatory — it is the control the whole experiment turns on.

## 2. Labels allowed (generation-quality ONLY)

`correctness`, `format_validity`, `constraint_satisfaction`, `groundedness`,
`reasoning_correctness`. All are objective, externally checkable per example.

## 3. Labels OUT of scope

`tool safety`, `unsafe action risk`, `governance`, `power-seeking`, `policy violation`,
`trust score`. These belong to the **Trust Observable Architecture**, a different track. The
schema validator **rejects** any `label_type` outside the allowed set, so a governance label
cannot accidentally enter this pipeline.

## 4. Baselines required

- **Chance / majority-class** — the floor.
- **`hidden_only`** (pooled + last-token final hidden) — the decisive control. The question is
  Bhava *vs / over* this, never Bhava vs chance alone.
- **Selectivity control (Hewitt–Liang)** — same probe trained on **randomly permuted labels**;
  report `selectivity = real_acc − control_acc` so a high-capacity probe fitting noise is caught.

Feature sets evaluated separately: `bhava_only`, `cg_state_32d`, `delta_bhava_only`,
`hidden_only`, `hidden_plus_bhava`, `hidden_plus_cg_state`.

## 5. What counts as success (the scientific rule)

Bhava usefulness is declared **only if both hold**, with statistics:

```
bhava_only  >  chance            (95% bootstrap CI of the gap excludes 0)
AND
hidden_plus_bhava  >  hidden_only (95% paired bootstrap CI of the delta excludes 0)
```

The second condition is the real test: Bhava must add signal **beyond** generic hidden features.
Beating chance alone is **not** success (hidden states may carry everything).

## 6. Decision categories (pre-registered)

| Decision | Condition | Meaning |
|----------|-----------|---------|
| `INSUFFICIENT_DATA` | too few labels or CIs too wide to resolve | get more data before concluding |
| `NO_SIGNAL` | bhava ≈ chance **and** hidden ≈ chance | task not decodable from this model at all |
| `HIDDEN_ONLY_SIGNAL` | hidden_only > chance, bhava_only ≈ chance | Bhava **not** load-bearing → park |
| `BHAVA_WEAK_SIGNAL` | bhava_only > chance but **not** > hidden_only, and no complementary gain | weak, redundant with hidden → park |
| `BHAVA_COMPLEMENTARY_SIGNAL` | hidden_plus_bhava > hidden_only (significant) | Bhava adds signal over hidden → **continue** |
| `BHAVA_STRONG_SIGNAL` | bhava_only ≥ hidden_only **and** hidden_plus_bhava improves further | Bhava strongly load-bearing → **continue** |

## 7. What parks Bhava for generation

`NO_SIGNAL`, `HIDDEN_ONLY_SIGNAL`, `BHAVA_WEAK_SIGNAL` → the ontology adds nothing decodable over
hidden states; **park** Bhava as a generation lever (and the wrapper redesign with it). Only
`BHAVA_COMPLEMENTARY_SIGNAL` / `BHAVA_STRONG_SIGNAL` justify continuing — and even then this is a
*probe* (correlation): a causal generation test (steer along the direction, measure objective
output change) would be a separate, later, pre-registered step.

## 8. Honesty / controls

- Train/test split (no leakage), k-fold where data is small, fixed seeds.
- Probes are **lightweight** (logistic / ridge; optional small MLP) and regularized; capacity is
  capped so the probe doesn't memorize.
- Report selectivity, bootstrap CIs, paired comparisons vs `hidden_only`.
- A `BHAVA_STRONG_SIGNAL` on a self-referentially-trained ontology is still only evidence the
  **value** is decodable — it does not prove the wrapper's `ΔBhava` path can use it.
- No subjective/coherence judgement enters any decision.
