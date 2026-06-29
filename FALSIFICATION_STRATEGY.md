# Symbol-U — Falsification Strategy

> **Type:** scientific foundation document (research track). No code. No implementation.
> Companion documents: `THEORY_FORMALIZATION.md`, `SCIENTIFIC_ROADMAP.md`.
> Purpose: define what would *uniquely support* and what would *genuinely falsify* the
> original Symbol-U theory — at the level of the **theory**, not any implementation.

## 3. Observations that would UNIQUELY support the theory

Excluded as non-unique (sentence embeddings / sentiment already satisfy them): "predicts
sentiment," "clusters emotion." The discriminating predictions:

- **P1 (pseudowords).** Novel varṇa sequences with **no lexical meaning** predict human
  ratings of the *sound* (valence / size / binding) above chance. Lexical models
  structurally cannot do this — there is no lexical entry to look up.
- **P2 (cross-linguistic universality).** The same phoneme sequence elicits the same
  response across speakers of unrelated languages.
- **P3 (ontology-specific).** The theory's *particular* `a(·)` beats both **random
  relabelings** and **generic acoustic baselines** (sonority, vowel height) — i.e., it is
  not merely textbook sound symbolism.
- **P4 (composition).** Reordering varṇas changes the reading in **human-predictable** ways
  (requires `F`).
- **P5 (independent attestation).** Poles match Sanskrit phonetic-tradition sources the
  lexicon authors did not write.

## 4. Observations that would FALSIFY the theory (not the implementation)

Run on **sound-rated human data with pseudowords**, never English lexical meaning:

- **F1.** On pseudowords, `a(·)` predicts human sound-ratings no better than chance →
  falsifies **Ax1**.
- **F2.** Random relabeling of `a(·)` does equally well → the ontology is arbitrary
  (falsifies **A2/A3**, **Level B**).
- **F3.** No cross-linguistic stability beyond acoustic baselines → falsifies **A3/P2**.
- **F4 (requires `F`).** Order has no human-predictable effect beyond a bag → falsifies
  **Ax2**.
- **F5 (requires `F`).** The emergent CSR / essence predictions match human data no better
  than the unigram sum → falsifies **Ax3**.

## 5. Three levels of claim — what supports each, what cannot distinguish them

| Level | Claim | What supports it | What it **cannot** be shown by |
|---|---|---|---|
| **A** | a useful representation exists | any discrimination result | — (weakest; even sentiment qualifies) |
| **B** | it reflects the **proposed ontology** | the **shuffle / relabel ablation** (real ≫ permuted) | any result *without* a relabel control |
| **C** | the ontology derives from **Sanskrit varṇa acoustics** | gloss-free **acoustic-only** signal + **cross-linguistic** + Sanskrit attestation | any **English-only** or **gloss-using** result |

**What cannot distinguish them:** any correlation with English lexical meaning conflates A
with B/C; any result lacking the relabel control cannot separate A from B; any English-only
result cannot reach C. **Everything done so far (v3 / v4 / O1.5) bears only on A — and only
the weak +0.07 shuffle margin gestures at B. No experiment to date bears on C.**

## 6. Independent evidence (no LLM, no policy, no English lexical similarity), ranked

1. **Pseudoword psycholinguistics** — human ratings of nonce varṇa sequences vs theory
   predictions. *Strongest:* isolates sound-intrinsic meaning with zero lexical confound;
   directly tests Ax1 / P1.
2. **Cross-linguistic corpus statistics** (Blasi-style) — do the varṇa→meaning associations
   recur above chance across unrelated languages' lexicons? Tests P2 / A3.
3. **Independent Sanskrit philological attestation** — do classical phonetic-tradition
   attributes match the poles? Tests whether glosses are author-invented (anti-circularity).
4. **Acoustic-perception studies** — do "binding / liberating" map to measurable perceptual
   axes?
5. **Historical linguistics** — sound change vs meaning stability (weak; can even
   *contradict* if cognates retain meaning through sound change).
6. **Glossed human judgments** — *weakest / circular* if raters see meaning.

## 7. The single minimal decisive experiment

**A pre-registered pseudoword sound-symbolism study.** Construct nonce words systematically
varying (i) varṇa composition and (ii) order. Naive participants (ideally across ≥2
unrelated language backgrounds) rate only the **sound** on the theory's claimed axis
(binding/liberating, or valence/arousal); no glosses, no language cue. Predictions derived
from `a(·)` (and `F`, for the order factor) are **registered before data**. Decision tests:

- **(a)** predictions beat chance? → **Ax1**
- **(b)** beat a **random relabeling** of `a(·)`? → **Level B** (the ontology specifically)
- **(c)** beat **generic acoustic** baselines? → is it the *ontology* or just known sound symbolism?
- **(d)** does **order** behave as predicted? → **Ax2** (requires `F`)

Passing (a)+(b)+(c) is strong evidence the *specific* ontology carries sound-intrinsic,
non-arbitrary semantic information (Level B, approaching C); failing (b) falsifies the
ontology as arbitrary. This single experiment maximizes information because it tests the
theory's **unique** claims (sound-intrinsic, ontology-specific, compositional,
lexically-empty) with **none** of the implementation's confounds (English, glosses, LLM,
bag aggregation).

**Caveat:** the order factor (d) and any CSR / emergence test **require `F` to be specified
first**. The unigram version (a–c) does not — it needs only `a(·)`, which exists.

## 8. Verdict on falsifiability (the most important conclusion)

- **Atomic claim (Ax1):** **falsifiable now** — needs only `a(·)` plus the pseudoword study.
- **Distinctive claim (Ax2 / Ax3, ρ\*, CSR):** **not currently falsifiable** — `F` is undefined.
- **Required before any implementation continues:** (1) a mathematical definition of `F`
  (ordered composition over the attribute sequence, including emergence), and (2) a
  pre-registered mapping from ρ\* outputs to **observable** human / corpus quantities.
  Absent these, no implementation can test the emergent theory; it can only re-test the
  atomic one.

## Implementation caution (binding)

No further English LLM-controller or policy work should proceed until either **S1/S2/S3**
support the atomic claim, or **S0** specifies ρ\* well enough to test the emergent claim
(see `SCIENTIFIC_ROADMAP.md`).
