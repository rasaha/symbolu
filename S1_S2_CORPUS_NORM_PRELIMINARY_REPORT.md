# S1 / S2 — Offline Corpus-Norm Preliminary (EARLY SIGNAL ONLY)

> **Type:** offline preliminary. **Run *after* the pre-registration was committed**
> (`S1_S2_PSEUDOWORD_PREREGISTRATION.md`, commit `0380687`). This is **not** S1/S2.
> It is a **confounded corpus proxy**: corpus words carry lexical meaning, the norm *is*
> the word's meaning, and sound→meaning correlation is genuinely small even when real.
> **It can rule a strong clean signal in or out; it cannot prove or falsify the theory.**
> Reproduce: `python -m symbolu_neural.s1_s2_corpus_prelim.run <data_dir>`. Does not touch
> v3/v4/O1.5 controller code.

## Method (brief)

- **Target norms (independent, human-rated):** Warriner et al. (2013) valence (V),
  arousal (A), dominance (D); AFINN valence (AF). N = **2500** words (3–12 letters),
  25 distinct varṇa keys.
- **a(·) predictor:** per-word varṇa attribute composition — created/destroyed polarity
  features (balance, tension, coherence) and emergent-valence votes.
- **Controls:** random relabel of the varṇa→polarity map (**K = 200** permutations, null
  distribution); generic acoustic baseline (vowel/consonant counts & ratios, length);
  word length; (raw phonetic substrate available, not needed once acoustic ≈ 0).
- **Metric:** 5-fold cross-validated R² (out-of-sample variance explained).

## Results

| norm | a(·) full R² | a(·) polarity R² | acoustic R² | length R² | relabel null (mean / p95) | real percentile | Δ a over acoustic |
|---|---|---|---|---|---|---|---|
| Valence (Warriner) | 0.001 | 0.001 | 0.003 | 0.001 | −0.001 / 0.002 | **92%** | −0.005 |
| Arousal (Warriner) | 0.002 | −0.002 | 0.007 | 0.012 | −0.001 / 0.003 | **39%** | −0.004 |
| Dominance (Warriner) | 0.001 | 0.001 | 0.003 | 0.001 | −0.001 / 0.002 | **90%** | +0.003 |
| Valence (AFINN) | 0.014 | 0.018 | −0.026 | −0.009 | −0.017 / 0.011 | **98%** | +0.010 |

## Interpretation — what this CAN conclude

- **No meaningful predictive signal.** Across all four human norms, the varṇa attribute
  table explains **≤ 2% of variance** (R² 0.001–0.018), and on the broad Warriner norms
  **≈ 0%** (R² ≤ 0.002). There is **no strong, clean, ontology-specific phonological signal**
  predicting human affect from the varṇa table. Had the atomic claim been *strong* and
  English-applicable, it would have shown here; it did not.
- **Relabel result is mixed and effect-size-negligible.** On 3 of 4 norms the real table
  sits above most relabels (92% / 90% / 98%), but arousal is *below* the relabel median
  (39%), and — decisively — the absolute R² at those percentiles is ~0.001–0.018. Being
  "above a near-zero null by a negligible margin" is **not** evidence of ontology-specificity.
- **The one non-trivial cell (AFINN valence: R² 0.018, 98th pct, +0.010 over acoustic)** is
  on the **smallest, most polarity-curated** norm (AFINN lists deliberately affect-laden
  words), where the generic acoustic baseline itself goes *negative*. At 1.8% variance it is
  within the range of generic sound symbolism and far too small to act on.

## Interpretation — what this CANNOT conclude (discipline)

- **It does NOT falsify Ax1.** Falsifying the atomic claim requires the pre-registered
  **pseudoword** study (no lexical confound; the theory's claimed binding/liberating axis;
  adequate power). A confounded near-null is *consistent with* both "weak real sound
  symbolism" and "no effect."
- **It does NOT confirm anything.** The mixed 90–98th-percentile relabel result is too weak
  and too small to claim the ontology carries signal.
- **It does NOT reach Level B or C.** No clean ontology-specificity (Level B) is shown, and
  Sanskrit-specific derivation (Level C) is entirely out of scope for an English corpus.

## Verdict

**INCONCLUSIVE, leaning toward "no meaningful signal."** The preliminary provides **no
positive early indication** that would justify resuming implementation — consistent with the
binding caution in the foundation documents. It does **not** settle the atomic claim either
way. The decisive test remains the pre-registered **pseudoword sound-symbolism study (S1/S2)**
with human raters, relabel and acoustic controls, and adequate power.

## Caveats (restated)

1. Corpus words have lexical meaning → the norm is confounded with semantics; this is a
   proxy, not the registered test.
2. Sound symbolism is a *small* effect in principle (published valence-from-phonology
   correlations ≈ r 0.1–0.2); a near-null here is weakly suggestive, not conclusive.
3. English input + transliteration + lexicon glosses are all present here — the three
   confounds the registered pseudoword study is designed to remove.
