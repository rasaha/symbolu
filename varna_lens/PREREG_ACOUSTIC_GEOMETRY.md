# PREREG — Acoustic Coordinate Geometry (F as a deterministic transform)

> **Status:** pre-registered, not yet run. **Date:** 2026-06-25.
> **Type:** representational-efficiency study (NOT an information-channel claim).
> This document is frozen before data collection. Hypotheses, datasets, controls, metrics, and decision
> rules below are committed in advance; results go in a separate `RESULTS_ACOUSTIC_GEOMETRY.md`.

## 0. Framing — and what this study explicitly is *not*

`F(word)` is a **deterministic acoustic coordinate transform**: it maps a word's phonological form to a
structured low-dimensional vector (the varṇa binding/liberating poles, per-position sign pattern from the
vowel-attachment rule, and the derived `emergent_valence`). We treat F as a **change of representation**,
not as a source of new information.

We **concede the information-theoretic argument up front**: F is a deterministic function of the phoneme
string, so by the data-processing inequality it creates **no Shannon information** beyond that string
(`I(Y; F | phonemes) = 0`). This study therefore makes **no claim** that F "sees what embeddings cannot."

The data-processing inequality bounds *information*, not *computation*. Deterministic, zero-information
transforms (Fourier features for coordinate MLPs, kernel feature maps, PCA/whitening, positional encodings,
syntactic/prosodic parses) have repeatedly changed the **learnability** of a target — its sample
complexity, optimization conditioning, controllability, or generalization — without adding entropy. The
question here is whether F is such a transform **for some form-aligned task**, or merely a decorative
re-encoding whose specific geometry does no causal work.

**Honest prior (pre-committed).** F is *lossy* and its compositional core is a **shallow syllabic/prosodic
parse** plus a hand-authored per-varṇa table. The right reference class is POS/dependency/prosody parses,
**not** Fourier/PCA. The syntax precedent says such transforms help when (a) aligned to the task and (b)
hard for the model to learn — and that the benefit **fades as models scale and learn the structure
themselves**. Phonological structure is highly learnable from text, so we expect any F advantage to be
**narrow (form-specific / low-resource) and scale-fragile**. We pre-register the tests that could
*overturn* this prior.

## 1. Hypotheses

**Primary (H_geom).** On **form-aligned tasks**, F improves at least one of **sample efficiency**,
**controllability**, or **interpretive structure**, relative to raw token embeddings, at matched capacity —
and the advantage is attributable to F's *specific geometry*, not to generic added dimensionality.

Decomposed, pre-registered sub-hypotheses (each independently falsifiable):

- **H1 (sample efficiency).** `E ⊕ F` reaches a target metric with fewer labeled examples than `E` alone,
  with the **inductive-bias signature**: the gap is largest in low-data and **shrinks** as data grows.
- **H2 (controllability).** Intervening on an F-axis produces a **predictable, monotone** change in the
  generated output (causal, low-variance), more so than intervening on matched baselines.
- **H3 (interpretive structure).** F yields lower **MDL / probe complexity** for form-aligned labels — a
  low-complexity reader on `E ⊕ F` beats one on `E` (and on the controls).
- **H4 (geometry attribution).** The advantage survives the control ladder (§4): F beats random-projection
  and label-shuffled-F (its *content* matters), and is benchmarked against syllable-only, panphon, and
  byte/char (its *competitiveness* as a phonological prior).

**Explicitly NOT tested here** (would mis-measure F): conditional mutual information (already conceded
zero); **asymptotic full-data accuracy** (a deep reader can internally compute F, so any real effect must
wash out with enough data — testing there guarantees a misleading null).

## 2. Candidate task classes (form-aligned; operationalized)

Each task is chosen because its target plausibly depends on **form**, where a phonological prior could be
aligned. For each we pre-state the target, dataset source, and reader.

1. **Naming / brand-name generation.** Target: human-rated fit/appeal of generated names to a stated brief
   (e.g. "fast, light, premium"); secondary: preference vs. a no-F baseline palette. Data: a held-out brief
   set + blind human raters (pre-registered rubric). Reader: light generation head / ranking model.
2. **Sound-symbolism prediction.** Target: established sound-symbolic judgments — bouba/kiki (round vs.
   sharp), mil/mal magnitude, high/low-vowel size — on **pseudowords** (no lexical confound). Data:
   pseudoword sets from the sound-symbolism literature + collected human ratings. Reader: linear/shallow
   probe (this is the cleanest H3 test).
3. **Poetic / mantra-like generation.** Target: rhyme/meter/euphony adherence and human-rated "incantatory"
   quality under constraints. Data: constrained generation prompts; objective prosody metrics + blind
   raters. Reader: generation head + automatic prosody scorers.
4. **OOV / neologism interpretation.** Target: predict properties/associations of **novel** words (coined
   neologisms, rare proper names) where token embeddings are fragmented or absent. Data: neologism sets +
   typo-perturbed words; held-out so no memorization. Reader: shallow classifier/regressor.
5. **Low-resource phonological–semantic transfer.** Target: cross-lingual cognate / loanword association or
   a phonological-semantic label in a low-resource language. Data: cognate sets; low-resource lexicons.
   Reader: shallow transfer probe.

> Tasks 2 and 4 are the **primary** falsification arenas (cleanest form-dependence, least lexical
> confound). Tasks 1 and 3 carry the controllability/interpretive-structure claims. Task 5 tests the
> embedding-poor regime.

## 3. Representations under test

- **E** — frozen base-LM token/subword embedding of the word (the conditioning baseline; the thing to beat *over*).
- **F** — the varṇa coordinate vector: per-varṇa `binding_state`/`liberating_state` embeddings (fixed),
  the vowel-attachment **sign pattern**, and `emergent_valence`. Deterministic, label-independent, frozen.

## 4. Control ladder (matched dimensionality & losslessness)

The controls isolate **F's specific geometry** from "merely having extra structured dimensions." All
concatenated reps are **capacity-matched** (same added dimensionality; same reader; same compute/budget).

| # | Representation | Isolates |
|---|---|---|
| C0 | raw **E** | baseline |
| C1 | E ⊕ **F** | the proposal |
| C2 | E ⊕ **random projection** (to F's dim) | is it just dimensionality / compression? |
| C3 | E ⊕ **random orthogonal transform** of F's inputs | does rotation alone help? (should not) |
| C4 | E ⊕ **label-shuffled F** (varṇa→pole map permuted across vocabulary) | do the *varṇa values* matter, or only the syllabic skeleton? |
| C5 | E ⊕ **syllable-structure-only** (F with pole values stripped; parse kept) | is all the work done by the prosodic parse, table inert? |
| C6 | E ⊕ **panphon / articulatory** distinctive features | the principled learned phonological prior F must beat |
| C7 | E ⊕ **byte/char** features (ByT5/CANINE-style) | the strong form-aware baseline |

C4 is the geometry-level analogue of this project's **relabeling-invariance / scrambled-control** discipline:
if C1 ≈ C4, F's *content* is inert and only its structure carried signal.

## 5. Metrics

Pre-registered, per task; reported with bootstrap 95% CIs.

- **Sample efficiency (H1):** accuracy/score vs. number of training examples (learning curves at
  n ∈ {8, 16, 32, 64, 128, 256, 512, full}); area-under-learning-curve and examples-to-threshold.
- **Controllability (H2):** for a unit intervention on each F-axis, the **monotonicity rate** and
  **effect-size/variance** of the corresponding output change, vs. matched interventions on controls.
- **Interpretive structure (H3):** **MDL** (Voita–Titov online codelength) and **probe selectivity**
  (Hewitt–Liang control-task gap) for a low-complexity reader.
- **Optimization (secondary):** steps/epochs to a target loss; loss-surface conditioning.
- **Generalization (secondary):** OOD / compositional generalization to unseen phoneme combinations.
- **Scale sweep (gating):** all of the above repeated across ≥3 base-model sizes to measure whether gains
  **persist or vanish** with scale.

## 6. Protocol

1. Freeze the base LM; freeze E. Build F and all controls C2–C7 at matched dimensionality.
2. For each task: train **shallow/light readers** (linear, then a small MLP) on C0–C7. Shallow readers are
   required — deep readers can internally recompute F and wash out the very effect under test.
3. Sweep training-set size for learning curves; repeat across base-model sizes for the scale sweep.
4. ≥5 seeds per cell; report mean ± bootstrap CI. Pre-register `MIN_EFFECT` per task before running.
5. Blind human evaluation (tasks 1, 3) with a fixed rubric and shuffled, source-masked outputs.

## 7. Pre-registered decision rules

Evaluated per task, then aggregated:

- **R1 — table inert.** If F beats **C0 (raw)** but **not C5 (syllable-only)** → the varṇa table adds
  nothing; the work is the prosodic parse. **Verdict: drop the lexicon, keep (at most) the parse.**
- **R2 — weaker phonological prior.** If F beats **C5** but **not C6 (panphon)** → F is a *weaker*
  phonological prior than principled articulatory features. **Verdict: not a new representation; use panphon.**
- **R3 — real representational result.** If F beats **C6 (panphon)** at matched capacity, **or** delivers
  clearly better **controllability (H2)** / **sample efficiency (H1)** than all controls → **F is a genuine
  representational result** for that task class. (Must also beat C2/C3/C4 to attribute it to geometry, not
  dimensionality or rotation.)
- **R4 — small-data prior, not a channel.** If any gains **vanish at scale** (shrink to within CI as
  base-model size / data grow) → report F as a **small-data / low-resource inductive prior**, explicitly
  **not** a universal semantic channel.
- **R0 — null.** If F ≈ C0 across tasks, or ties C2/C3/C4 wherever it beats C0 → F's specific geometry is
  inert; **no admission to reasoning.**

No post-hoc rescue: a rule that fires is reported as-is. Negative and null results are first-class outcomes.

## 8. Firewall (binding, regardless of results)

- **F is NOT evidence for factual claims.** F never grounds, scores, or adjudicates truth (C×R×S). Treating
  F as evidence would revive the already-falsified sound→meaning channel. This holds *even if* H_geom
  succeeds — a representational/efficiency win does not make F referentially informative.
- **F may enter Vikalpa / creative generation immediately.** As a licensed, clearly-labelled *speculative*
  seed (the existing `reflect.py` use), no further test required.
- **F may enter reasoning ONLY** in **form-aligned or embedding-poor regimes**, and **only after** passing
  §7 (specifically R3, with geometry attribution via C2–C4, and subject to the R4 scale caveat). Admission
  is **per-task-class**, never global. In all other regimes (in-vocab referential-semantic reasoning), F
  stays firewalled to Vikalpa by default.

## 9. Predicted outcomes (recorded prior, for calibration)

Stated so the prediction is itself falsifiable:

- Task 2 (sound-symbolism, pseudowords) and Task 4 (OOV): **most likely** non-null for F over raw — but
  **likely matched or beaten by C6/C7** (panphon/byte). Expected landing: R2 or a weak R3.
- Tasks 1, 3 (naming, mantra): plausible **controllability/interpretability** win (H2/H3) even at parity on
  accuracy — the most defensible route to R3.
- In-vocab semantic side-checks: **null** (R0), consistent with the firewall.
- Across the scale sweep: gains **shrink** (R4) — the inductive-bias signature.

A result that **violates** this prior — e.g., F beating panphon on accuracy *and persisting at scale* —
would be the genuinely surprising, publishable finding and the only thing that upgrades F from "small-data
prior" to "representation worth integrating into reasoning broadly."

## 10. Threats to validity

- **Capacity confound** — mitigated by matched-dimension controls C2/C3.
- **Reader-depth confound** — mitigated by mandating shallow readers; deep readers nulls the effect.
- **Lexical leakage in task design** — mitigated by pseudowords (T2) and held-out neologisms (T4).
- **Multiple comparisons** — pre-registered `MIN_EFFECT`, fixed task/metric list, CI reporting, no metric
  hunting.
- **Human-rater bias** — blind, source-masked, fixed rubric, inter-rater agreement reported.
- **"Exists a basis" vacuity** — neutralized by requiring F to be *fixed and label-independent* and to beat
  *label-shuffled* and *random* transforms; alignment must be earned, not searched for post hoc.
