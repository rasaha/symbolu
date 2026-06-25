# Results — H1 Interpretive Convergence (the first positive result)

> Hypothesis from `VARNA_PROFILE_METHOD.md`. **H1:** given a word's varṇa profile, independent readers
> produce *convergent* readings — i.e. the profile reliably **channels** interpretation. This is a
> property of the system as a generative instrument; it is **not** a claim of veridical decoding (H3,
> falsified). Harness: `convergence_test.py`. Verdict by rule.

## Design
8 words; for each, the varṇa profile under **real / scrambled / random** lexicons, plus a **no-seed
floor** (readers write a sketch with no profile at all). 5 independent blind readers each authored a
2-sentence character sketch per item, seeing only the chain (never the word or condition). **Convergence
= mean pairwise content-word cosine** of the 5 readers' sketches for an item (higher = readers channeled
to a more shared reading). Bootstrap CIs over words.

## Results

| condition | convergence |
|---|---|
| **real profile** | **0.218**  (95% CI 0.181–0.257) |
| scrambled profile | 0.229 |
| random-symbolic profile | 0.177 |
| no-seed floor | 0.076  (95% CI 0.037–0.149) |

- **Δ real − no-seed = +0.142** → real's CI floor (0.181) is well above the floor (0.076):
  **H1 SUPPORTED** — the profile channels readers to a shared reading ~3× the no-seed baseline.
- **Δ real − scrambled = −0.011** (95% CI −0.048 … +0.032) → the channeling is **structural**, not from
  the specific sound→gloss mapping (consistent with the six prior nulls).
- **Δ real − random = +0.041** (95% CI +0.013 … +0.071) → coherent propensity vocabulary channels
  modestly **more** than neutral nouns (a small, real "vocabulary" effect).

### VERDICT: **INTERPRETIVE_CONVERGENCE_SUPPORTED (structural)**

## What this does and does not establish

**Establishes (positive):**
- The varṇa profile is a **reliable generative instrument**: the same deterministic profile reliably
  steers independent readers toward a *shared* reading, far above free association. Combined with H0
  (determinism), this is the empirical backbone of the Varṇa Profile Method as a *creativity / reflection
  scaffold*. This is the first hypothesis in the program to return positive — and it's the one the IP
  actually needs.

**Does NOT establish (held honest):**
- It does **not** show the reading is *true* of the word (that's H3 — falsified).
- The convergence is **structural**: a scrambled lexicon (same vocabulary, permuted mapping) channels
  *equally well* (real ≈ scrambled). So the channeling comes from the **structured profile + its evocative
  propensity vocabulary**, not from the specific sound→propensity attachment being veridical.

**Honest one-liner:** *the varṇa profile works as a consistent generative scaffold (readers converge on a
shared reading); that usefulness is a property of the structure and vocabulary, not evidence the sound
→meaning mapping is true.*

## Limitations / how to strengthen
- N = 8 words, 5 readers, lexical-cosine metric, generic no-seed floor. To harden: more words/readers, a
  sentence-embedding convergence metric, counterbalanced presentation, and a pre-registered MIN_EFFECT.
- Next honest claim to test: **H2 (utility)** — do users *prefer* profile-seeded reflections/names over a
  no-scaffold baseline (blind, counterbalanced)? That productizes the instrument.

## Reproducibility
`python convergence_test.py --emit` (blind items), then 5 blind readers, then
`--score readers.json --keyfile items.json`. Reader sketches + key archived in
`RESULTS_H1_CONVERGENCE_READERS.json`; `convergence_test.score(readers, key)` recomputes the numbers.
