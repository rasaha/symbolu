# Phonetic Stuttering Evaluation Report

**Date:** 2025-12-12 21:16:04
**Corpus Size:** 200
**Hypothesis:** "Phonetic stuttering" is a measurable failure mode correlated with specific phonetic features.

---

## Executive Summary

This evaluation tests whether phonetic features (sibilants, stops, nasals, fricatives, stop-ending ratios)
correlate with text "brokenness" (repetition, fragments, poor flow) in the Symbol-U renderer output.

**Verdict:** **HYPOTHESIS PARTIALLY SUPPORTED** ~

Correlations found, but optimizer improvements are negligible.

---

## Methodology

### 1. Brokenness Metrics

**Brokenness Score** is computed from three components:

- **Repeated 3-gram rate** (40% weight): Ratio of unique 3-grams that appear multiple times
- **Fragment indicator score** (35% weight): Frequency of sentence-starting hedges ("Consider", "To clarify", etc.)
- **Stopword + punctuation ratio** (25% weight): Stopword density and abrupt short sentences

**Score range:** [0, 1], where 0 = clean, 1 = maximally broken

### 2. Phonetic Features

Phoneme-proxy features extracted using pattern matching:

- **Sibilants**: s, z, sh sounds (patterns: `\bs[aeiou]`, `sh`, etc.)
- **Stops**: p, t, k, b, d, g sounds
- **Nasals**: m, n sounds
- **Fricatives**: f, v sounds
- **Stop-ending ratio**: Proportion of words ending in stop consonants

### 3. Corpus

- **200 synthetic outputs** generated deterministically
- Outputs vary in brokenness level (low/medium/high)
- Prompts cover diverse topics (ML, physics, philosophy, etc.)

### 4. Optimization

Phonetic reranker applies two strategies:

1. **Fragment diversification**: Replace repeated sentence starters with synonyms
2. **Stop-ending reduction**: (minimal, to avoid semantic changes)

---

## Results

### Baseline Evaluation

**Brokenness Statistics:**

| Metric | Value |
|--------|-------|
| Mean brokenness | 0.186 |
| Min brokenness | 0.014 |
| Max brokenness | 0.290 |
| Outputs with high brokenness (>0.7) | 0.0% |
| Mean 3-gram repetition rate | 0.075 |
| Mean fragment score | 0.248 |

**Top 5 Phonetic Predictors:**

| Rank | Feature | Correlation (r) | Effect Size |
|------|---------|-----------------|-------------|
| 1 | sibilant_density | -0.735 | large |
| 2 | stop_ending_ratio | +0.412 | medium |
| 3 | fricative_density | -0.400 | medium |
| 4 | stop_density | +0.365 | medium |
| 5 | nasal_density | +0.115 | small |

**Analysis:**

- **sibilant_density** shows large correlation (r=-0.735)
- **Stop-ending ratio** correlation: r=+0.412 (medium)

### Optimized Evaluation

**Brokenness Statistics (After Optimization):**

| Metric | Value | Delta |
|--------|-------|-------|
| Mean brokenness | 0.108 | -0.078 |
| Outputs with high brokenness (>0.7) | 0.0% | +0.0% |
| Mean 3-gram repetition rate | 0.056 | -0.019 |
| Mean fragment score | 0.050 | -0.198 |

**Analysis:**

- Mean brokenness decreased by 0.078 (42.2% change)
- High-brokenness output rate changed minimally (<5%)

---

## Conclusions

### Evidence Assessment


**Correlations Found:**

The analysis identified phonetic features with non-negligible correlations to brokenness:

- sibilant_density: r=-0.735 (large effect)
- stop_ending_ratio: r=+0.412 (medium effect)
- fricative_density: r=-0.400 (medium effect)
- stop_density: r=+0.365 (medium effect)

This suggests some relationship between phonetic patterns and text quality metrics.

**Optimization Impact:**

The phonetic reranker produced negligible improvements (<5% change).
This suggests that phonetic optimization is NOT an effective intervention.

### Final Verdict

**HYPOTHESIS PARTIALLY SUPPORTED** ~


**Recommendation:** Phonetic features show some correlation, but the optimizer is ineffective.
Further research needed before production implementation.

---

## Limitations

1. **Synthetic Data**: Evaluation used synthetic outputs, not real renderer outputs
2. **Phoneme Approximation**: Letter patterns are rough proxies for actual phonemes
3. **Correlation ≠ Causation**: Observed correlations may be spurious
4. **Limited Optimization**: Reranker only addresses fragments, not stop-endings

## Future Work

- Test on real Symbol-U renderer outputs
- Use actual phonetic transcription (IPA) instead of letter patterns
- Implement more sophisticated optimization (synonym substitution, rephrasing)
- Test on human-rated quality scores

---

*This report was generated automatically by the Phonetic Stutter Evaluation Module.*
