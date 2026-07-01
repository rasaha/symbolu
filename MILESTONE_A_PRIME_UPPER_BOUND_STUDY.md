# MILESTONE_A_PRIME_UPPER_BOUND_STUDY

> **STATUS — Scope specification for Milestone A′ (Existing-Data Upper-Bound Analysis).**
> Documentation only. No code, no datasets downloaded, no harness, no Stage A change, no
> weakened caveat. This document *scopes* a desk study; it does not run it and selects no
> dataset. Per `IMPLEMENTATION_ROADMAP.md`, Milestone A′ is the cheapest desk-level falsifier
> and runs **before** the validation harness (Milestone B) is built.
> **Candidate hypothesis · Not validated · Stage A untouched · No Sanskrit privilege ·
> No semantic claims · Glossary-independent inputs required · Preserve ⊥.**
> **structure, not validated meaning.**

## 0. Position in the roadmap

Milestone A established that the **only admissible provenance** for a gloss-independent essence
table `E` is externally-measured sound-symbolism norms (path 3), and left Milestone A
**unresolved** pending a defensible source. Milestone A′ discharges that dependency *and*
doubles as a free atomic falsifier: it asks, using **existing public data only**, whether such
norms carry *any* semantic signal beyond phonology — before a single line of harness code is
written. A clean null here terminates the program at the lowest possible cost.

**Scope boundary (important).** A′ estimates the conditional information recoverable from
**static, non-order-manipulated existing data**. It is therefore an upper bound on the
**additive / atomic-essence** branch only. Per the revised atomic-gate logic
(`IMPLEMENTATION_ROADMAP.md`, Milestone B), a null here **does not logically falsify the
order-dependent L2 hypothesis** — existing norm corpora cannot probe order. A′'s null is
decisive for the additive branch and, given negative priors, makes funding the order branch a
**labelled resource decision**, not a logical entailment. This caveat is load-bearing and is
repeated in §6–§7.

## 1. Research question

Stated precisely:

> **Is there any measurable conditional mutual information between externally-sourced
> sound-symbolism dimensions `E` and a lexical semantic observable `Y`, after conditioning on a
> raw phonological/acoustic feature baseline `Phonology`?**

Estimand:

```
I(Y ; E | Phonology)
```

where
- **`E`** = externally-measured sound-symbolism / pseudoword norm dimensions, projected to
  unit-level (phoneme/varṇa) or word-level features. `E` is a **perceptual** mapping (human
  ratings), deliberately *not* an articulatory feature table — see §4.
- **`Y`** = a lexical semantic observable (e.g. VAD norms; lexical-semantic embedding
  coordinates), externally sourced.
- **`Phonology`** = a raw phonological/acoustic feature description of the same items (the
  baseline `E` must beat).

The decision-relevant reading: if conditioning on phonology drives the `E→Y` association to
≈0, then `E` is phonology in disguise (the path-2 collapse), and no gloss-independent
downstream model built on `E` can recover meaning beyond sound. The whole semantic program then
has no non-circular substrate worth implementing.

## 2. Dataset sourcing criteria

A candidate dataset (or a pairing of datasets supplying `E`, `Y`, and `Phonology` for common
items) is **admissible** only if it satisfies **all** of:

1. **Public or citable** — retrievable and referenceable; provenance documented.
2. **Externally measured** — produced independently of this project.
3. **Gloss-independent** — `E` values not derived from, or selected using, the meanings of the
   target items (sound-symbolism collected on lexically-empty or sound-only judgments).
4. **Not derived from Sanskrit dictionary meanings** — no leakage from the lexicon the broader
   program would later predict; no Sanskrit-gloss provenance in `E`.
5. **Contains sound-symbolic or pseudoword ratings** (for `E`) or is unambiguously
   unit-mappable to such ratings.
6. **Mappable to phoneme / unit-level features** — so `E` and `Phonology` can be defined on a
   common unit inventory and aggregated to the level at which `Y` is observed.
7. **Sufficient sample size** — enough jointly-observed items for cross-validated prediction and
   conditional-information estimation with usable uncertainty (target stated at run time in the
   pre-registration; underpowered → *inconclusive*, not null).
8. **Includes or can be paired with semantic observables `Y`** — VAD norms / embeddings for the
   same items, joinable by a stable key (orthographic/IPA form).

**No dataset is committed in this document.** Selection happens in the run-time
pre-registration, against these criteria, and is frozen (with `sha256`) before any analysis.

## 3. Candidate dataset classes (illustrative — *candidate only*, none selected)

Scoped as **classes**, not final choices. Named examples are illustrations of the class, not
selections.

| Class | Supplies | Status |
|---|---|---|
| Pseudoword sound-symbolism ratings | `E` (perceptual, gloss-free) | **candidate only** |
| Bouba/kiki & shape–size–affect norms | `E` (cross-modal sound→property) | **candidate only** |
| Cross-linguistic iconicity ratings | `E` (sound→meaning iconicity, gloss-independent design) | **candidate only** |
| Phoneme-level affective / symbolic norms | `E` projected to units | **candidate only** |
| VAD lexical norm datasets | `Y` (valence/arousal/dominance) | **candidate only** |
| Lexical semantic embeddings | `Y` (distributional meaning coordinates) | **candidate only** |
| Phonological feature datasets | `Phonology` (articulatory/acoustic baseline) | **candidate only** |

A viable A′ run will typically **pair** one `E`-class source, one `Y`-class source, and one
`Phonology`-class source over a shared item set. Each pairing must independently satisfy §2.

## 4. Baselines

`E` must be tested against — and must **beat** — the full baseline set; otherwise it collapses
into one of them:

1. **Phonological similarity** — the **decisive** baseline. The conditioning variable in
   `I(Y;E|Phonology)`. If `E` adds nothing over this, it is sound, not symbolism.
2. **Raw phonetic / acoustic features** — articulatory/acoustic feature vectors (place, manner,
   voicing, sonority, formant summaries). `E` (perceptual ratings) must add incremental signal
   over this physical description; if not, `E` ≡ phonetics (the path-2 collapse).
3. **Bag-of-units** — `E` aggregated as an unordered multiset, to confirm no order claim is
   smuggled in at the A′ (atomic) stage.
4. **Length / frequency** — word length, syllable count, corpus frequency as nuisance
   predictors of `Y`; `E` must beat these.
5. **Sentiment / lexicon** — if `Y` is affective, a sentiment-lexicon predictor, to ensure `E`
   is not merely re-deriving a known affect lexicon.
6. **Relabel / random controls** — permute the unit→`E` assignment (`K` permutations,
   marginals preserved) to build the null; the real `E` must exceed the upper tail (e.g. 95th
   percentile) of this null on the incremental statistic.

**Binding rule:** `E` must beat **phonology** (and survive relabel/random). Conditioning on
phonology is the heart of the test; any signal that does not survive it is generic sound, and
A′ returns ⊥.

## 5. Analysis design (intended methods — *no code in this document*)

1. **Common item set & keys.** Join `E`, `Y`, `Phonology` over items sharing a stable
   orthographic/IPA key; document coverage and attrition.
2. **Feature construction.** Build `E` features (unit-level norm values aggregated to the item
   level under a *generous* aggregation — the goal is an upper bound, so do not artificially
   restrict the predictor); build `Phonology` features; build baseline features (§4).
3. **Predictive relation to `Y`.** Fit cross-validated predictors of `Y` from (a) `Phonology`
   alone and (b) `Phonology + E`. The **incremental** cross-validated performance
   (ΔR² / Δlog-likelihood, out-of-fold) is the operational signal.
4. **Conditional-information estimate.** Approximate `I(Y;E|Phonology)` via (i) the incremental
   predictive performance above and/or (ii) a residualization route (predict `Y` from
   phonology, test `E` on the residual) and/or (iii) a conditional-MI estimator (e.g. a
   conditional k-NN/KSG-style estimator) where sample size permits. **Estimator caveat:**
   incremental CV performance is a **lower bound** on true CMI, but it is an **upper bound on
   what a constrained, gloss-independent downstream model could recover** — and the latter is
   the decision-relevant quantity. MI estimators are positively biased at small `N`; bias
   controls and the relabel null guard against false positives.
5. **Baseline comparison.** Run the same incremental test against every §4 baseline; the real
   `E` must exceed the **relabel/random** null and beat **phonology** specifically.
6. **Cross-validation.** Item-level k-fold with leakage control (related word forms kept in the
   same fold); report out-of-fold metrics only.
7. **Uncertainty.** Bootstrap confidence intervals on the incremental statistic; permutation
   p-value against the relabel null; sensitivity to aggregation choice and to `Phonology`
   feature richness.
8. **Failure state.** If no incremental signal exceeds the baselines (CI includes 0; below the
   relabel tail), **return ⊥** — reported as such, never a forced reading.
9. **Collinearity guard.** If `E` and `Phonology` are too collinear to separate (variance
   inflation beyond a pre-set bound), the result is **inconclusive**, not null — the test could
   not attribute signal either way.

All choices (datasets, features, aggregation, metric, thresholds, `K`, folds) are frozen in a
run-time pre-registration **before** analysis; any change is a logged amendment made before
results are seen.

## 6. Termination criteria

| # | Condition | Outcome |
|---|---|---|
| 1 | **No admissible dataset source** satisfies §2 | **Terminate Milestone A** — `E` cannot be sourced non-circularly; the Milestone A gate fires retroactively. |
| 2 | Dataset exists but **`I(Y;E|Phonology) ≈ 0`** (within pre-registered band) | **Terminate** the additive/atomic-essence program. *Caveat (consistency with revised roadmap):* this is decisive for the additive branch and, given negative priors, a labelled **resource-decision** stop for the program; it does **not** logically refute an order-dependent effect A′ cannot probe from static data. |
| 3 | Signal exists but **does not beat phonology / relabel / random** | **Terminate** — generic sound symbolism, not a non-circular semantic `E`; collapses into the baseline. |
| 4 | **Signal survives** (beats phonology, relabel, random; CI excludes 0) | **Milestone A′ passes.** A defensible `E` source with conditional signal exists; building the **Milestone B synthetic harness** (B.0) becomes worthwhile. A′ pass is a *license to proceed*, **not** validation of any semantic claim. |
| — | `E`/phonology too collinear to separate, or underpowered | **Inconclusive** — repeat with a better-separated pairing or larger `N`; not a pass/fail. |

## 7. Scientific caveats (binding)

- This study **does not validate Symbol-U.**
- This study **does not validate Sanskrit / varṇa privilege.**
- This study **does not validate operators** (L1) or any decoder (L3).
- This study **only determines whether a non-circular `E` has any empirical signal worth
  testing** beyond phonology — at the additive level recoverable from existing data.
- A **negative result is a valid, expected outcome.** Priors are negative (S1/S2 corpus norms
  R²≈0–2%; O1.5 ~12:1 sound-over-meaning; synonyms varṇa-disjoint). Terminating here is the
  roadmap working as designed.
- A **pass licenses the next cheap step only** (the synthetic harness); it is not evidence for
  the order-dependent hypothesis, which A′ cannot test.

## 8. Deliverable & next step

This document is the **scope** of Milestone A′. The next artifact (separate, on approval) is the
**run-time pre-registration**: the specific `E`/`Y`/`Phonology` dataset pairing selected against
§2, the frozen features/aggregation/metric/thresholds, and the `sha256` freeze — authored
*before* any analysis. No harness, no `F`, no decoder, and no Milestone B work precedes a §6
outcome.

---

> **Candidate hypothesis · Not validated · A′ scopes a desk falsifier only · No dataset
> committed · Stage A untouched · `⊥` preserved.**
> **structure, not validated meaning.**
