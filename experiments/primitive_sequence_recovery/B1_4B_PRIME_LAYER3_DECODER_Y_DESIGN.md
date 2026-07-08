# B1.4b′ — Layer-3 Decoder & Y Validation Design

**Status:** Design memo (docs-only) for **Layer 3** of a **future B1.4b′** study. Not code, not a dataset, not a
run.
**Governed by:** `stage_a_prime_coverage.py` (`8d4b097`), `STAGE_A_PRIME_SAMPLE_THREE_LAYER_TRACE.md`
(`af9935b`), `PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`, `B1_4B_TARGET_Y_ADMISSIBILITY_AUDIT.md`,
`SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**No Y matrix. No semantic validation. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

---

## 1. Purpose

This memo designs **Layer 3** — the decoder/probe `y = D(z)` and its independent target `Y` — for a **future
B1.4b′** study (Stage A′ as L1). It is **not** for the original frozen B1.4b, which stays as-is. It defines what
Layer 3 would be, how it would be validated against baselines, and exactly what remains **blocked** before any
run. It builds no `Y`, runs nothing, scores nothing, and **claims no semantic success**.

---

## 2. Current state

- **Stage A′ solves repo-local L1 coverage** — Sanskrit 107/107 and English 92/92 fully decomposable
  (`8d4b097`), operators orthogonal, leakage audit clean.
- **Sample trace shows L1→L2 success** — 20/20 words decomposed, 20/20 F-3 features computable (`af9935b`).
- **L3 remains blocked** — no independent `Y` exists; every sample was `A_PRIME_L3_BLOCKED_NO_Y`.
- **Original B1.4b remains blocked** — Stage A′ is **not** substituted into it.
- **B1.4b′ requires separate pre-registration** — this memo is design input for that, not the pre-registration
  itself.

---

## 3. Layer definitions

- **L1 — Stage A′ phoneme/operator sequence:** `word → phonemes → M_σ = expm(Σ_j f_{σ,j} G_j)` (orthogonal;
  Stage A′ module, not frozen Stage A).
- **L2 — F-3 operator-interaction latent `z`:** commutator / non-commutativity features over the operator
  sequence.
- **L3 — decoder/probe `y = D(z)`:** a bounded map from the structural latent `z` to predicted attribute values.
- **Validation:** compare `y` to an **independent frozen `Y`** under the full baseline suite; only beating all
  baselines counts.

---

## 4. Layer-3 question

> **Can a bounded decoder from the F-3 structural latent `z` predict independent human attribute norms `Y`
> better than the phonological, bag, shuffle, random, sentiment, and null baselines?**

This is a question about **structural-latent → attribute prediction beyond phonology**, not about meaning in the
abstract. The burden is on the F-3 decoder to beat **every** baseline; otherwise the honest answer is a
baseline-explains label / `⊥`.

---

## 5. Target `Y` requirements

`Y` is admissible only if **all** hold:

- **Independently collected** — by a process unrelated to Symbol-U / Stage A′.
- **Human-produced or otherwise non-varṇa-derived** — not generated from the varṇa/phoneme pipeline.
- **Attribute/feature based, not dictionary-definition matching** — a profile of attributes, not the word's
  definition nor a match-to-definition score.
- **Frozen before training/scoring** — `Y`, concepts, attributes, exclusions hash-locked before any decoder fit.
- **Not LLM-generated** — unless explicitly marked **pilot-only** and never used as an evidence target.
- **Matched to decomposable Stage A′ concepts** — every `Y` concept must decompose fully under Stage A′
  (`A_PRIME_EN`/`A_PRIME_SA`), or it is excluded (coverage-overlap gate, §18).

---

## 6. Candidate `Y` sources

- **McRae (2005) feature-production norms** — primary candidate (human-produced concept features).
- **CSLB (2014) concept property norms** — primary candidate (largest property set).
- **Binder (2016) experiential feature ratings** — primary candidate (cleanest ~65-dim attribute structure).
- **SWOW / association norms** — **secondary / triangulation** only (associations are not attributes).
- **VAD / sentiment / concreteness / frequency** — **controls / covariates ONLY**, never the primary `Y`
  (VAD ≈ the sentiment baseline → would guarantee `SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS`).
- **Dictionary/gloss-derived labels** — **rejected** (definitional circularity).
- **Unconstrained LLM-generated `Y`** — **rejected as evidence** (decoder-in-disguise, unauditable); permitted
  only as an explicitly-labelled **pilot-only** sanity check, never scored as evidence.

None acquired here; selection is deferred to the coverage-overlap audit + `Y` freeze (§18).

---

## 7. Decoder `D` options

Allowed decoder/probe families:

- **Regularized linear regression/classification** — ridge (continuous `Y`) or L2-logistic (binary attributes);
  **default first evidence pass.**
- **PLS / reduced-rank regression** — allowed if pre-registered and justified (structured multi-attribute `Y`).
- **Low-capacity learned probe** — only in a **separate pre-registration**, with capacity caps and a
  phonology-only learned control.
- **No high-capacity / overfit model in the first evidence pass** — no deep nets, no unbounded boosting.

`D` is the **decoder**; the **probe** is the tested comparison against baselines. A decoder producing plausible
output is **not** evidence (probe ≠ decoder).

---

## 8. Decoder capacity parity

F-3 and **every** baseline must use the **same** probe family, the **same** regularization search grid, and the
**same** train/test protocol and folds. No method may receive extra capacity, extra features-per-parameter, or a
different CV scheme. Any F-3 advantage must not be attributable to a capacity or protocol difference.

---

## 9. Baseline suite

F-3 must be tested against **all** of, at matched capacity:

- **plain phonological features** (pooled articulatory `f_σ`) — the decisive control,
- **phonological similarity** (sound-neighborhood, meaning-unrelated),
- **bag-of-phonemes/varṇas** (order-destroyed histogram),
- **shuffled-order** (F-3 recomputed on shuffled phoneme sequences),
- **random / relabel operators** (operators reassigned at random),
- **length / frequency**,
- **sentiment / lexicon**,
- **chance / null** (label-permutation / marginal),
- **semantic-only baseline** (if applicable to the `Y`/task).

Beating some but not all is **not** signal.

---

## 10. Primary endpoint

- **F-3 decoder must beat the phonological baseline** (plain-phonological **and** phonological-similarity) —
  **primary**, because Stage A′ is phonology-parameterized.
- **F-3 decoder must beat the bag / shuffle / random-relabel baselines** — **co-primary**, because F-3's claim
  is order-dependent composition.
- **Failure to beat phonology → `F_COLLAPSES_TO_PHONOLOGY`.** Failure to beat order baselines →
  `BAG_OR_SHUFFLE_EXPLAINS` / `RANDOM_RELABEL_EXPLAINS`. Both (phonology **and** order) must pass, with
  multiple-comparison correction, for any positive label.

---

## 11. Train/test split

- **Concept-level splits** — folds partition *concepts*; no concept appears in both train and test.
- **No leakage between train and test concepts** — including no shared inflections/near-duplicates across the
  split.
- **Frozen preprocessing** — normalization, imputation/drop, any reduction fixed before fitting.
- **No post-hoc attribute selection** — attribute set + reliability floor frozen before results are seen.
- **No tuning on test labels** — all hyperparameters chosen by inner CV on training folds only.

---

## 12. Metrics

- **Cross-validated R² / correlation / balanced accuracy** — task-appropriate to `Y`, averaged over attributes
  with distribution reported.
- **Δ vs phonology** — F-3 minus plain-phonological and minus phonological-similarity (decisive contrasts).
- **Δ vs shuffle / bag / random-relabel** — F-3 minus each order/structure control.
- **Confidence intervals** — bootstrap CIs on every score and Δ.
- **Permutation test** — label-permutation null for the primary Δ, if feasible.
- **Holm (or equivalent) correction** — across the baseline-contrast family; primary endpoint named in advance.

---

## 13. Invalid-run conditions

The run is **invalid** (report the matching label, never a signal) if any hold:

- **no independent `Y`** (`Y_NOT_INDEPENDENT` / `B1_4B_PRIME_LAYER3_BLOCKED_NO_Y`),
- **`Y` created after seeing F-3** (post-hoc target),
- **dictionary/gloss leakage** into `Y`, features, or decoder (`DECODER_LEAKAGE_INVALID`),
- **decoder capacity mismatch** between F-3 and baselines,
- **missing phonology baseline**,
- **Stage A′ silently substituted into the old B1.4b** (must be a new B1.4b′),
- **post-hoc feature changes** (F-3 list / Stage A′ inventory altered after results),
- **semantic interpretation without endpoint success** (claiming meaning absent a passed primary endpoint).

---

## 14. Layer-3 (design-stage) terminal labels

- **`B1_4B_PRIME_LAYER3_READY_FOR_PREREG`** — decoder + `Y` + baselines + endpoint specified; ready to draft the
  B1.4b′ pre-registration.
- **`B1_4B_PRIME_LAYER3_BLOCKED_NO_Y`** — no independent `Y` secured (current state).
- **`B1_4B_PRIME_LAYER3_BLOCKED_COVERAGE_OVERLAP`** — `Y` concepts don't sufficiently overlap Stage A′-decomposable
  concepts.
- **`B1_4B_PRIME_LAYER3_DECODER_SPEC_READY`** — the decoder/probe family + parity + splits are specified.
- **`B1_4B_PRIME_LAYER3_LEAKAGE_RISK`** — a gloss/target-leakage path is present and unresolved.
- **`B1_4B_PRIME_LAYER3_INCONCLUSIVE`** — the design question cannot be resolved as specified.

**This memo emits:** `B1_4B_PRIME_LAYER3_DECODER_SPEC_READY` (decoder/baseline/endpoint design is complete) **+**
`B1_4B_PRIME_LAYER3_BLOCKED_NO_Y` (no independent `Y` yet). It is **not** `READY_FOR_PREREG` until `Y` and
coverage-overlap gates (§18) clear.

---

## 15. Future evidence-run labels (defined, NOT claimed)

These belong to a future B1.4b′ **evidence run** and are **not** asserted here:

`L1_L2_L3_ATTRIBUTE_SIGNAL` · `F_COLLAPSES_TO_PHONOLOGY` · `BAG_OR_SHUFFLE_EXPLAINS` ·
`RANDOM_RELABEL_EXPLAINS` · `SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS` · `Y_NOT_INDEPENDENT` ·
`DECODER_LEAKAGE_INVALID` · `NULL_RETURN_BOTTOM` · `INCONCLUSIVE`.

Only `L1_L2_L3_ATTRIBUTE_SIGNAL` would be positive, and only by beating **all** baselines on the pre-registered
endpoint. **No `L1_L2_L3_ATTRIBUTE_SIGNAL`, no `ONTOLOGICAL_SIGNAL`, no semantic-success claim is made in this
memo.**

---

## 16. Relation to Stage A′

- **Stage A′ only fixes L1 coverage** — it does not supply `Y`, a decoder, or any semantic result.
- **Layer 3 still needs an independent `Y`** — the binding blocker (`B1_4B_PRIME_LAYER3_BLOCKED_NO_Y`).
- **A future B1.4b′ must be separately pre-registered and frozen** — adopting Stage A′ as L1 explicitly.
- **No silent substitution** of Stage A′ into the original B1.4b / B1.4a artifacts, which stay as-is.

---

## 17. Expected outcome

The expected honest result remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`.** Stage A′ is **explicitly
phonology-derived** — its operators are functions of articulatory features — so the phonological baseline is
**decisive and, with fuller coverage, likely stronger**. Any F-3 decoder must still beat plain phonology; the
prior (sound-over-meaning; B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈ real ~0.967) points to it not doing
so. A faithful Stage A′ makes that eventual `⊥` **more trustworthy**, not more favorable. This design exists to
make the verdict honest and falsifiable, not to manufacture a positive.

---

## 18. Next gate

In order (none performed here; each needs separate explicit approval):

1. **Independent `Y`-source acquisition / metadata approval** — obtain a candidate norm set's concept list +
   attribute schema (Binder first; McRae/CSLB fallback). Until then, Layer 3 is `B1_4B_PRIME_LAYER3_BLOCKED_NO_Y`.
2. **Coverage-overlap audit** — count `Y` concepts that decompose fully under Stage A′; require ≥ the
   pre-registered floor (≥ ~100). If too few → `B1_4B_PRIME_LAYER3_BLOCKED_COVERAGE_OVERLAP`.
3. **B1.4b′ pre-registration** — only after (1) and (2) clear: freeze `Y`, decoder family, baselines, endpoint,
   splits, metrics, thresholds. Only then, under further authorization, an evidence run.

No implementation, dataset, or run is authorized by this document.

---

## 19. Boundary statement

> B1.4b′ Layer-3 decoder/Y design completed. No Y matrix created. No semantic validation performed. No evidence
> freeze declared. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
