# Results — acoustic-signal test, LETTER-BASED ENGLISH variant

> **Variant run.** Same pre-registered harness, thresholds, wordlist, judge protocol, metric, and the
> **corrected lexicon** (commit `38e38d3`). The ONLY change: the English subset is segmented by **letters**
> (read literally, like IAST — e.g. son = s+o+n, sun = s+u+n, f→Pha) instead of by **pronunciation** (g2p).
> Sanskrit stays literal; the other languages stay mapped to Sanskrit varṇas by sound. Run via the same
> blind LLM sub-agent judges as the other confirmatory runs. Pre-registered verdict rule, unchanged.

## Why this was run
A homophone collision (son/sun both /sʌn/ → identical reading) was raised as a possible cause of failure.
Letter-based reading makes them differ (son: Escapism·Closure·Delusion; sun: Escapism·Contraction·Delusion).
The question: does distinguishing them recover meaning, or is the homophone collision cosmetic?

## PRIMARY VERDICT (recorded before explanatory analysis)

| metric | value |
|---|---|
| accuracy(real) | **0.197**  (95% CI 0.134–0.268) |
| accuracy(scrambled, avg 2 seeds) | 0.240 |
| chance (1/K) | 0.200 |
| **Δ = real − scrambled** | **−0.043**  (95% bootstrap CI **−0.118 … +0.031**) |

### VERDICT: **NO_SIGNAL**
Δ's 95% CI contains 0; real sits at chance and does not beat the scrambled lexicon. The letter-based English
reading does not recover meaning.

acc(real) by language: en 0.222, sa 0.192, ja 0.167, ur 0.167, zh 0.167 — all at/near chance.
**English-only subset** (the part that changed, n=36): acc(real) = 0.222, Δ = **+0.042**.

## Comparison

| run (corrected lexicon) | acc(real) | acc(scrambled) | Δ (95% CI) | verdict |
|---|---|---|---|---|
| **pronunciation English** (g2p) | 0.173 | 0.280 | −0.106 (−0.185 … −0.028) | NO_SIGNAL |
| **letter English** (this run) | 0.197 | 0.240 | −0.043 (−0.118 … +0.031) | NO_SIGNAL |
| (old pre-correction, pronunciation) | 0.205 | 0.260 | −0.055 (−0.142 … +0.031) | NO_SIGNAL |

Letter-based English is *slightly less negative* than the pronunciation version (real moves from 0.173 →
0.197, back to chance; Δ from −0.106 → −0.043), and the English-only Δ is a hair positive (+0.042). But this
is **within noise**, real still does **not** beat scrambled, and **no threshold is passed**. The English-only
nudge to 0.222 (vs 0.20 chance, n=36) is **trend only, not signal** — and even "trend" is generous.

## Interpretation
Switching English to a letter/spelling basis did **not** produce signal. Distinguishing *son* from *sun* is
**cosmetic**: it yields two different readings but neither recovers the word's meaning, and the decisive
control is unchanged — the real letter→meaning map does not beat a scrambled one. The homophone collision
was an *illustration* of sound-blindness, not the cause of NO_SIGNAL; the cause is that the lexicon carries
no meaning information regardless of how words are segmented. (Note: reading English by letters also converts
the *acoustic*-root claim into an *orthographic*-root claim, on the least-phonetic major writing system.)

**Bottom line: NO_SIGNAL under letter-based English, just as under pronunciation. The segmentation change
does not rescue the lexical claim.**
