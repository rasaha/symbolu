# B1.3 Gate-5 Probe Validity Review

## 1. Scope

Reviews the **inference strength** of the Gate-5 feasibility probe only — specifically whether it justifies
the hard `RAW_VARNA_FEATURE_MODEL_NOT_FEASIBLE_STOP_NOW`, or whether that should be weakened to
`HIGH_RISK_NEEDS_ADJUDICATION`. Validity review only; no implementation, no probe rerun, no models, no
scoring. Does not change prior B1/B1.1/B1.2 results, authorizes no evidence run, and makes no
`LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit / semantic-truth / Track-B
claim. **Structure, not validated meaning.**

## 2. What the probe validly tests

- Whether **raw varṇa-sequence similarity correlates with semantic similarity** across 2,412 word pairs
  (Spearman ρ = 0.008, Pearson 0.006; inside the permutation band [−0.027, +0.029]).
- Whether **varṇa-nearest-neighbor words are semantically closer than baseline** (nn semantic lift = 0.010).
- It is directly relevant to any **distance-/kernel-/whole-sequence-similarity** raw-varṇa model: such a model
  relies on exactly the geometry the probe found absent. For that family, the probe is decisive-negative.

## 3. What the probe does NOT fully rule out

Honestly, a global distance correlation and a whole-sequence nearest-neighbor test do **not** mathematically
exclude:

- a **sparse, learned per-varṇa→feature model** — if only a few of the ~34 varṇas carry meaning and the rest
  are noise, whole-sequence distance is noise-dominated (ρ≈0) while a **regularized model that isolates the
  informative varṇas** could still predict features. The probe cannot see this;
- a fully specified **pre-existing** varṇa→feature contribution table (none is known, but the probe doesn't
  test one);
- a **trained model under strict held-out evaluation** (route D), which is a *different* estimator than a
  distance metric.

Caveat on all three: any such model would need **independent justification**, a **disjoint train/test split**,
and must **never be tuned to G** — else it is circular and cannot be evidence. And the whole-sequence
nearest-neighbor lift being ≈0 already makes even a sparse per-varṇa signal *unlikely* (shared varṇas confer
no semantic lift on average) — unlikely, but not excluded.

## 4. Why the result is still damaging

- ρ≈0 → **no detectable global raw-varṇa/semantic geometry**.
- nn-lift≈0 → **sound-nearest words are not meaning-nearest**.
- This is **convergent** with every prior finding: B1/B1.1 random/scrambled controls not beaten; Track G
  `RANDOM_POLARITY_EXPLAINS`; B1.2 `V_deranged ≈ V_real`, `V_random ≥ V_real`, top-1 own-G at chance.
- Therefore the **burden on any future raw-varṇa model is very high**, and the *expected* outcome of even a
  held-out learned model is null.

## 5. Decision review

```
DECISION: WEAKEN_TO_RAW_VARNA_FEATURE_MODEL_HIGH_RISK_NEEDS_ADJUDICATION
```

**Reason:** `NOT_FEASIBLE_STOP_NOW` is a **universal** claim ("no non-circular model can work"), and a
whole-sequence **distance** probe cannot support a universal — it leaves one **specific, non-circular
candidate uncovered**: a **sparse learned per-varṇa→feature model evaluated on a disjoint held-out split**
(route D). By the review's own criterion (weaken *iff* a specific non-circular candidate exists that the
distance probe does not cover), that candidate qualifies. Consistent with the adversarial-honesty mandate — do
not overclaim a negative any more than a positive — the honest label is **HIGH_RISK**, not infeasible.

**This is not a rescue and not encouragement.** The prior is heavily null (§4); the burden is high; and even a
positive held-out result would test *learnable phoneme→meaning generalization*, **not** Symbol-U's specific
ontology. Weakening only means the universal "impossible" claim is unwarranted from this probe — the question
"is one clean held-out learned-M development probe worth running, or do we close?" should be decided
**explicitly** in a dedicated adjudication, not buried inside a correlation statistic.

## 6. Consequence

The Gate-5 record is amended from a hard STOP to **HIGH_RISK_NEEDS_ADJUDICATION**. The autonomous workplan
does **not** resume Gates 6–8 (they still presuppose a *chosen* feasible model); instead the next step is the
dedicated adjudication that decides between (a) one disjoint-split learned-M development probe under strict
anti-circularity rules, or (b) closure.

## 7. Next gate

```
next gate: B1_3_VARNA_TO_FEATURE_RULE_ADJUDICATION
```

(If that adjudication finds no admissible non-circular route, it routes to `VARNA_LINE_CLOSURE_MEMO`.)

## 8. Final status block

```
document:                   B1.3 Gate-5 probe VALIDITY REVIEW (review only; nothing run)
prior Gate-5 decision:      RAW_VARNA_FEATURE_MODEL_NOT_FEASIBLE_STOP_NOW
amended decision:           WEAKEN_TO_RAW_VARNA_FEATURE_MODEL_HIGH_RISK_NEEDS_ADJUDICATION
basis:                      distance probe cannot support a universal "infeasible"; sparse held-out learned-M uncovered
prior nulls:                convergent and heavily against (burden very high; expected null)
B1 / B1.1 / B1.2:           UNCHANGED (B1.1 RANDOM_OR_SCRAMBLED_MATCHES)
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
EVIDENCE_FREEZE:            NONE (development finding only)
next gate:                  B1_3_VARNA_TO_FEATURE_RULE_ADJUDICATION
```

**Structure, not validated meaning.** The Gate-5 probe is decisive against distance-based raw-varṇa models and
convergent with all prior nulls, but it cannot justify a universal infeasibility claim; the decision is
weakened to high-risk, one specific held-out candidate remains to be adjudicated, and no prior result is
changed, rescued, or claimed as evidence.
