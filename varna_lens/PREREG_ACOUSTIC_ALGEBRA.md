# PREREG — Acoustic Algebra, Operator #1: `compose`

> **Status:** pre-registered, not yet run. **Date:** 2026-06-25.
> **Scope:** ONE operator, ONE law. This document does **not** claim an acoustic algebra exists.
> Frozen before data collection; results go in a separate `RESULTS_ACOUSTIC_ALGEBRA.md`.

## 0. What this is and is not

This tests a single, minimal question: does the first candidate operator — **composition** — have any
**faithful, leverage-providing empirical content**, or is it a formally-declared function with none?

- It is **not** a claim that a full acoustic algebra exists.
- It is **not** a claim that sound determines meaning.
- It introduces **no** other operators. Resonance, emergence, cancellation, attenuation, amplification are
  **future operators only if `compose` passes** — they are out of scope here.

## 1. Motivation

A **formal** algebra is cheap: any set with any closed operation qualifies. That threshold is uninteresting.
The scientific object is an operator that is (a) **faithful** — it is a homomorphic image of a *real*
operation on sounds/names, not a free-floating formal game — and (b) **leverage-providing** — its behavior
predicts something external and/or simplifies a downstream task beyond what the controls already give.

So this prereg deliberately tests **one operator (`compose`)** and **one law** (a monotonicity /
compositional-consistency law, §3), with a homomorphism test (§4) against an external perceptual target
(§5). Naming an operator is not evidence; a passed law against controls is. Anything `compose` cannot earn
here, it does not get to assume.

## 2. Signature

- **Carrier `Z`** — the acoustic-state representation produced by the existing varṇa feature extractor:
  per-varṇa `binding_state`/`liberating_state` embeddings, the vowel-attachment **sign pattern**, and the
  derived `emergent_valence` (the same fixed, deterministic `F` from `PREREG_ACOUSTIC_GEOMETRY.md`).
- **Operator** — `compose : Z × Z → Z`.
- **Initial composition rule** — the **existing ordered varṇa-chain / vowel-attachment mechanism**: given
  units `a` and `b`, concatenate their phoneme sequences in order and re-run the deterministic reading on
  the joined sequence, yielding a single element of `Z` for the combined form. No new mechanism is invented.
- **Input/output types** — inputs are two `Z`-elements derived from pronounceable units (a syllable, a
  morph, a short name-part); output is one `Z`-element of the same type as any single-unit `F(·)`.
- **Closure condition** — `compose(F(a), F(b))` must lie in the **same representation type** as `F` of any
  word (same fields, same dimensionality, a valid reading). Operationally: closure holds iff
  `compose(F(a), F(b))` is identical in type/shape to `F(combine_real(a, b))` and re-readable by the engine.
  Closure failures (degenerate/empty readings) are logged and counted, not silently dropped.

## 3. Candidate law (exactly one)

We pick **monotonicity / compositional consistency**, not associativity (deferred — the vowel-attachment
rule is position-dependent, hence presumptively non-associative; testing associativity now would conflate
operator content with parse structure).

**L1 — binding-score monotonicity under composition.**
> Hold `B` fixed. If unit `A` has a stronger binding lean than `A′` (`bind_score(F(A)) > bind_score(F(A′))`),
> then the composed form preserves or predictably shifts the combined binding lean in the same direction:
> `bind_score(compose(F(A), F(B))) ≥ bind_score(compose(F(A′), F(B)))` (within a pre-registered tolerance),
> across a held-out set of `(A, A′, B)` triples.

`bind_score(·)` is the signed binding/liberating quantity already produced by `emergent_valence`
(binding_votes − liberating_votes, or its normalized form). L1 is a single, falsifiable, ordinal statement:
composition must not scramble the order it inherits from its parts. **Primary law metric:** rank-preservation
rate (fraction of triples satisfying L1) and Kendall's τ between `bind_score(A)−bind_score(A′)` and the
composed difference, with bootstrap 95% CIs, **versus the controls in §6**.

## 4. Homomorphism test

Define the **real-world operation** `combine_real(a, b)`: physically join two pronounceable units into one
larger pronounceable form (syllable+syllable, morph+morph, or name-part+name-part), as actually uttered.

Two tests:

- **H-commute (structural faithfulness).** Does the operator commute with real combination?
  `compose(F(a), F(b)) ≈ F(combine_real(a, b))`, measured as representation distance, against the §6
  controls. (For the chosen rule these may coincide by construction for some fields; report exactly which
  fields commute and which diverge — divergence is informative, not disqualifying.)
- **H-predict (semantic faithfulness — the make-or-break test).** Does the **composed representation**
  predict **human perception of the combined form** better than predicting it from the parts naively or
  from the controls? I.e., a low-complexity reader on `compose(F(a), F(b))` predicts the §5 human labels of
  `combine_real(a, b)` with higher accuracy than the same reader on shuffled/random/syllable/panphon/byte
  composition, at matched capacity.

A formal algebra can pass H-commute and still fail H-predict (faithful to *its own* mechanics, empty about
sounds). **H-predict is decisive.**

## 5. Human-judgment targets

Simple **perceptual** labels on the *combined* form — never factual semantics:

- heavy / light
- harsh / soft
- energetic / calm
- pleasant / unpleasant
- sacred / ordinary
- binding / liberating — **only** if explicitly framed to raters as an *internal interpretive impression*,
  not an objective fact (collected separately and flagged; never used as ground truth for factual claims).

Collection: blind, source-masked, fixed rubric, ≥N raters per item, inter-rater agreement reported. Items
are **pronounceable pseudo-combinations** (pseudoword + pseudoword) to remove lexical-meaning confounds,
plus a secondary real-name set for ecological validity.

## 6. Controls (matched capacity)

Every claim in §3–§4 is evaluated as `compose` **versus** the same operation built on:

- **raw token embedding** (baseline)
- **label-shuffled F** (varṇa→pole map permuted across vocabulary) — does the *ontology content* matter?
- **random projection** (to F's dim) — is it just dimensionality?
- **random binary operator** (a fixed random `Z×Z→Z`) — does the *specific composition rule* matter?
- **syllable-structure-only** (F with pole values stripped, parse kept) — is it just the prosodic parse?
- **panphon / articulatory** features composed the same way — the principled phonological prior to beat
- **byte / character** features — the strong form-aware baseline

All readers shallow and capacity-matched; ≥5 seeds; bootstrap CIs; `MIN_EFFECT` pre-registered per label.

## 7. Decision rules

Evaluated on H-predict (primary) and L1 (supporting), per label then aggregated:

- **R1 — ontology inert.** `compose` beats **raw** but **not syllable-only** → the varṇa ontology adds
  nothing over the prosodic parse. Keep (at most) the parse; drop the table's algebraic pretensions.
- **R2 — weak acoustic prior.** Beats **syllable-only** but **not panphon** → `compose` is a *weaker*
  phonological operator than articulatory features. Not a faithful operator worth its own algebra.
- **R3 — candidate faithful operator.** Beats **panphon** AND **shuffled/random** controls at matched
  capacity → `compose` has content attributable to its specific geometry. A faithful first operator.
- **R4 — candidate leverage-providing operator.** R3 holds AND `compose` predicts human judgments (H-predict)
  AND supports **controllable generation** (e.g., traversing composed `bind_score` steers a rated attribute
  monotonically) → `compose` earns a second test, and only then may a *second* operator be proposed.
- **R0 — stop.** None of the above (ties raw, or fails shuffled/random) → **stop all algebra claims.** F
  reverts to a **creative Vikalpa-only scaffold**; no operator, no calculus.

No post-hoc rescue; a fired rule is reported as-is. Null and negative results are first-class.

## 8. Firewalls (binding regardless of result)

- This does **not** prove sound determines meaning.
- This does **not** justify factual reasoning from varṇas (F is never evidence for facts).
- This does **not** establish a full algebra — it tests **one operator, one law**.
- A pass licenses only the *next* test, never an assumed structure. A second operator may be proposed only
  after `compose` reaches **R4**, and each future operator carries its own prereg, closure check, and
  consistency obligation against L1.

## 9. Predicted outcome (recorded prior, for calibration)

Honest prior: most likely **R1 or R2** — much of any signal will be the syllabic/prosodic parse, and panphon
will be hard to beat. H-commute likely partially holds by construction; **H-predict is the real gate** and
is where the prior expects the null. A result reaching **R3/R4** — `compose` beating panphon and predicting
human perception of combined pseudowords against controls — would be the genuinely surprising, reportable
finding and the only outcome that earns operator #2.

## 10. Output

- This document is the deliverable. **No code yet** — implementation deferred until explicitly requested.
- Datasets, readers, and the rater protocol are specified above to be built when the run is authorized.
