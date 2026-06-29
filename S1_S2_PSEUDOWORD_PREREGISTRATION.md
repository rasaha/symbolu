# S1 / S2 — Pseudoword Sound-Symbolism Study: PRE-REGISTRATION

> **Type:** pre-registration of a human-subjects psycholinguistic experiment. **No code.**
> Tests the **atomic** Symbol-U claims (Ax1 non-arbitrariness; Level-B ontology-specificity)
> on **lexically-empty** stimuli — the regime ordinary semantic models cannot reach.
> Companions: `THEORY_FORMALIZATION.md`, `FALSIFICATION_STRATEGY.md`, `SCIENTIFIC_ROADMAP.md`.
> This document is frozen before any data collection; analysis decisions below are committed
> in advance. A separate offline corpus proxy
> (`S1_S2_CORPUS_NORM_PRELIMINARY_REPORT.md`) is an *early signal only*, not this study.

## 1. Hypotheses

Let `a(·)` be the proposed varṇa attribute table, and for a pseudoword `w` let `A(w)` be a
pre-specified aggregation of its varṇas' attributes onto the theory's claimed axis
(binding↔liberating; secondarily valence/arousal/dominance/size).

- **S1 — Ax1 (non-arbitrariness).**
  - **H0₁:** `A(w)` does not predict human sound-ratings of pseudowords above chance.
  - **H1₁:** `A(w)` predicts human sound-ratings above chance.
- **S2 — ontology-specificity (Level B).**
  - **H0₂:** the *specific* `a(·)` predicts no better than (i) random relabelings of `a(·)`
    and (ii) a generic acoustic baseline.
  - **H1₂:** the *specific* `a(·)` predicts **incrementally** beyond both controls.

S2 is conditional: it is only interpretable if S1 rejects H0₁ (there must be a signal before
asking whether the signal is ontology-specific).

## 2. Stimulus design

- **N = 80 pseudowords**, monomorphemic, 2–3 syllables, 4–7 phonemes, phonotactically legal
  in the rating language(s).
- **Factor 1 — pole composition:** items pre-scored by `A(w)` and sampled to fill the full
  range (balanced quartiles of predicted binding↔liberating), so the predictor has variance
  by construction (this tests calibration, not the existence of variance).
- **Factor 2 — order (for a later S4 extension, recorded now):** for 20 items, include a
  varṇa-order-permuted twin holding the multiset constant. *Order is analyzed in S4, not
  S1/S2; pre-registered here only so stimuli support it.*
- **Counterbalancing:** length, syllable count, and stress pattern balanced across pole
  quartiles so they cannot proxy the predictor.
- Stimuli delivered as **audio** (primary) and IPA text (secondary); modality recorded as a
  covariate.

## 3. How pseudowords are constructed

1. Generate candidate phoneme strings by sampling varṇas under phonotactic constraints.
2. Compute `A(w)` from `a(·)` for each candidate.
3. **Exclude** candidates within edit-distance 1 of any real word (per a large wordlist in
   each rating language) and any candidate flagged by ≥1 of 3 native screeners as
   word-like or offensive.
4. Stratified-sample 80 to fill pole quartiles while balancing the §2 covariates.
5. Freeze the stimulus list + each item's `A(w)`, acoustic features, and (for S2) the
   relabel seeds, with a recorded `sha256`, **before** data collection.

## 4. Human-rating axes

Primary: **binding ↔ liberating** (the theory's own axis), 7-point bipolar scale, defined to
raters in neutral affective terms without varṇa/ontology language.
Secondary (standard, comparable to external norms): **valence, arousal, dominance, size**
(7-point). Raters judge **the sound**, explicitly instructed these are nonsense words with
no meaning. Axis order randomized; each item rated on each axis.

## 5. Inclusion / exclusion rules

- **Participants:** N ≥ 60 per rating language, native speakers, normal hearing (self-report),
  ≥2 unrelated language groups total (e.g., English + a typologically distant language) to
  support the later cross-linguistic milestone.
- **Attention checks:** ≥2 catch items (e.g., "rate this one at the far left"); exclude
  participants failing any.
- **Reliability:** exclude participants whose ratings correlate < 0.1 with the
  participant-mean profile (random responders).
- **Items:** exclude any item flagged post-hoc as a recognizable word by >20% of raters.
- **Pre-registered minimum:** ≥ 50 valid raters/language and ≥ 70 retained items, else the
  study is **underpowered → inconclusive** (not a pass/fail).
- Target power: detect a per-item predictor effect of r ≥ 0.30 at 80% power (drives N items).

## 6. Random-relabel controls (the Level-B test)

- Build the **null distribution** by randomly permuting the varṇa→attribute assignment
  `a(·)` **K = 1000** times (each permutation degrees-of-freedom-matched: same attribute
  marginals, applied consistently across all items), recomputing `A_perm(w)` and refitting
  the model.
- The real `a(·)` must fall **above the 95th percentile** of the permutation null on the
  primary effect statistic. This isolates "the *specific* mapping matters" from "*some*
  phonological aggregate correlates."

## 7. Generic acoustic controls (the not-just-known-sound-symbolism test)

Baseline acoustic feature set per item (no ontology): mean sonority, vowel height/backness
means, voicing ratio, stop/fricative/nasal/liquid proportions, syllable count, duration.
The specific `a(·)` must add **incremental** predictive value over this baseline (S2(ii)).

## 8. Statistical tests

- **Primary model (S1):** linear mixed-effects `rating ~ A(w) + (1|participant) + (1|item)`,
  per axis; primary axis = binding↔liberating. Effect = standardized β of `A(w)` and the
  item-level partial correlation.
- **S2(i) relabel:** permutation test — observed primary statistic vs the K=1000 relabel
  null (§6); report percentile and permutation p.
- **S2(ii) acoustic:** nested model comparison — ΔR²/likelihood-ratio of
  `[acoustic + A(w)]` vs `[acoustic]`; report incremental effect with CI.
- **Multiplicity:** primary axis is the single confirmatory endpoint; the 4 secondary axes
  are Holm-corrected and exploratory.
- All models, exclusions, and the primary axis are fixed here; any change is a logged
  amendment before unblinding.

## 9. Pass / fail thresholds (frozen)

- **S1 PASS:** standardized β of `A(w)` on the primary axis significant (p < 0.05) with
  |partial r| ≥ 0.20, in the predicted direction.
- **S2 PASS:** S1 passes **AND** real `a(·)` > 95th percentile of the relabel null
  (permutation p < 0.05) **AND** incremental ΔR² over the acoustic baseline significant
  (p < 0.05).
- **Headline support (atomic theory survives):** S1 PASS **and** S2 PASS.

## 10. What result would falsify Ax1 (non-arbitrariness)

`A(w)` predicts the primary axis **no better than chance** (β not significant, |partial r|
< 0.10) in an adequately powered sample. Then the proposed atoms carry no recoverable
sound-intrinsic signal — the foundational axiom is falsified, independent of ρ\*.

## 11. What result would falsify ontology-specificity (Level B)

S1 passes (there *is* a phonological signal) **but** the real `a(·)` lies **within** the
relabel null (permutation p ≥ 0.05) **and/or** adds **no** incremental value over the
generic acoustic baseline. Then any correlation is generic sound symbolism, not the *specific*
Symbol-U ontology — the ontology is not doing work.

## 12. What result would remain INCONCLUSIVE

- Underpowered (< 50 valid raters/language or < 70 retained items), or low rater reliability.
- `A(w)` and the acoustic baseline too collinear to separate (variance-inflation too high) →
  cannot attribute signal to the ontology vs. generic acoustics.
- S1 marginal (0.10 ≤ |partial r| < 0.20) → suggestive, not confirmatory; pre-registered as
  "repeat with larger N," not a pass.
- Direction mismatch (significant but opposite to prediction) → flagged as a specification
  problem in `a(·)` or the aggregation `A`, not a clean pass or fail.

## Scope notes

- This study tests the **atomic** claims only (Ax1, Level B). The **emergent** claim
  (Ax2/Ax3, ρ\*, CSR) is **out of scope** and cannot be tested until ρ\* (the function `F`)
  is specified (milestone S0).
- A clean S1+S2 PASS supports **Level B** (the ontology carries non-arbitrary sound-intrinsic
  signal); it does **not** by itself establish **Level C** (Sanskrit-specific derivation),
  which requires the cross-linguistic milestone (S6) and gloss-free acoustic isolation.
