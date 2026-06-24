# Results — non-lexical UTILITY test, CORRECTED-LEXICON re-run

> **This is the corrected-lexicon run.** Same pre-registered harness, scramble (pair-preserving),
> thresholds, wordlist, templates, judge rubric, and metric as `RESULTS_UTILITY_SIGNAL.md` — only the
> lexicon changed (8 source-corrected entries). The prior result stays attached to the pre-correction
> lexicon and is **not** merged with this one.

## Run identity
- **Lexicon version / commit:** `38e38d3`
- **Entries:** 34 consonants + 12 vowels · **Corrected letters:** Ca, Ja, Ma, Ra, Va, Śa, Ṣa, Sa
- **Test:** `varna_lens/utility_test.py` `emit_pairs` (124 words, one use_case each; real vs scrambled-seed0,
  order randomized & hidden; scramble permutes (worldly,counter) pole-PAIRS as units → preserves antonym
  pairing, +/− structure, gloss multiset, output length) → blind A/B LLM judges (sub-agents) scoring six
  1–5 dims (coherence/depth/usefulness/specificity/non_generic/fit) → `score_pairs`. **Judge mode: blind
  LLM (7 sub-agents).**

## PRIMARY VERDICT (recorded before any explanatory analysis)

| metric | value |
|---|---|
| utility(real) − utility(scrambled): **Δ** | **+0.067**  (95% bootstrap CI **−0.007 … +0.140**) |
| real-preferred rate | 0.556  (95% CI 0.472 … 0.641 — **includes 0.50**) |
| MIN_EFFECT (practical threshold) | 0.30 |

### VERDICT: **NO_UTILITY_SIGNAL**
95% CI(Δ) contains 0, and Δ (0.067) is far below MIN_EFFECT (0.30). No measurable utility advantage for the
real sound→propensity mapping over a pair-preserving scramble.

### Position-bias diagnostic
Judges preferred the second-shown artifact "B" 72× vs "A" 46× (6 ties). Splitting by where *real* was placed
(balanced 62/62): Δ(real=A) = **+0.012**, Δ(real=B) = **+0.122** — the effect tracks position, not content.
Because placement is balanced, position bias cancels in the aggregate (leaving the +0.067), but the bias is
again comparable to or larger than the effect. Judge unreliability persists.

### Per-use-case Δ (all sub-threshold)
| use_case | Δ |
|---|---|
| naming | +0.136 |
| affective | +0.060 |
| journaling | +0.050 |
| creative | +0.038 |

Every cell is below 0.30.

## Comparison vs old pre-correction lexicon

| | Δ (95% CI) | real-pref | position split (A / B) | verdict |
|---|---|---|---|---|
| **old (pre-correction)** | +0.070 (+0.008 … +0.133) | 0.573 | −0.050 / +0.190 | INCONCLUSIVE |
| **corrected (`38e38d3`)** | +0.067 (−0.007 … +0.140) | 0.556 | +0.012 / +0.122 | NO_UTILITY_SIGNAL |

Essentially the **same micro-effect (~0.07)**, still far below the product threshold and still confounded by
position bias. With the corrected lexicon the Δ CI now straddles 0, so the verdict is a **cleaner null**
(NO_UTILITY_SIGNAL) rather than the old borderline INCONCLUSIVE. The source correction did **not** improve
non-lexical utility. **trend: none toward utility signal.**

## Interpretation
The corrected source-aligned lexicon did **not** produce measurable non-lexical utility over a fair
(pair-preserving) scramble. Artifact quality remains dominated by the (identical) template and the lexicon's
general richness, both preserved by the scramble. No product claim of the real lexicon over a scrambled one
is supported. Not connected to C×R×S / Conscious Generation.
