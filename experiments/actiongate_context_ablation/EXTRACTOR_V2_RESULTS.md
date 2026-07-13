# EXTRACTOR_V2_RESULTS — Milestone: extraction + protected-span quality

> Improves the two bottlenecks from the naturalistic study ONLY (extractor instability, protected-span precision). No compressor, SCC, or USE. Existing corpus and ActionGate unchanged. Detector trained on DEV+VALIDATION; held-out is the honest generalization number. Deterministic.

- Corpus: **77** contexts (unchanged from the naturalistic study).

## Targets (preregistered)

- ✅ `heldout_instability_below_10pct`
- ✅ `all_domains_instability_below_10pct`
- ✅ `heldout_recall_is_1`
- ✅ `heldout_precision_gain_substantial`

## 1 · Extractor instability (before → after)

| scope | v1 baseline | v2 multi-stage |
|---|---|---|
| all splits | 14.7% | **1.2%** |
| held-out | 41.0% | **1.9%** |

**v2 instability by domain** (target < 10%):

| domain | v2 instability |
|---|---|
| cicd | 0.0% |
| database | 0.0% |
| iam | 0.0% |
| kubernetes | 6.8% |
| monitoring | 0.0% |
| network | 0.0% |
| payments | 0.0% |
| repo | 0.0% |
| secrets | 0.0% |
| storage | 0.0% |
| terraform | 0.0% |

## 2 · Protected-span detection (held-out generalization)

| detector | recall | precision | protected frac | deployable ceiling | oracle ceiling |
|---|---|---|---|---|---|
| baseline_keyword | 7.5% | 5.9% | 48.9% | 51.1% | 61.1% |
| trained_classifier | 97.9% | 100.0% | 38.1% | 61.9% | 61.1% |
| fail_closed_hybrid | 100.0% | 100.0% | 38.9% | 61.1% | 61.1% |

**Overall (all splits):**

| detector | recall | precision | deployable ceiling |
|---|---|---|---|
| baseline_keyword | 63.6% | 31.4% | 31.0% |
| trained_classifier | 97.8% | 100.0% | 66.7% |
| fail_closed_hybrid | 100.0% | 100.0% | 66.0% |

Held-out per-class recall (hybrid, vs full critical union): {'ENVELOPE_CRITICAL': 1.0, 'DECISION_CRITICAL': 1.0, 'ASSURANCE_CRITICAL': 1.0, 'STRUCTURAL': 1.0, 'NON_CRITICAL': 1.0, 'INTERACTION_ONLY': 1.0}.  Residual unprotected critical spans: **0**.

## 3 · Protected-span detection by domain (baseline → hybrid)

| domain | baseline R/P | hybrid R/P | hybrid deployable ceiling |
|---|---|---|---|
| cicd | 65.1%/32.0% | 100.0%/100.0% | 66.4% |
| database | 80.6%/34.7% | 100.0%/100.0% | 66.3% |
| iam | 44.8%/21.7% | 100.0%/100.0% | 69.4% |
| kubernetes | 59.5%/37.4% | 100.0%/100.0% | 58.3% |
| monitoring | 67.9%/22.6% | 100.0%/100.0% | 76.1% |
| network | 72.2%/23.9% | 100.0%/100.0% | 76.6% |
| payments | 67.6%/52.8% | 100.0%/100.0% | 46.1% |
| repo | 76.0%/25.5% | 100.0%/100.0% | 75.4% |
| secrets | 71.2%/37.1% | 100.0%/100.0% | 63.3% |
| storage | 54.8%/25.2% | 100.0%/100.0% | 69.0% |
| terraform | 61.5%/30.3% | 100.0%/100.0% | 66.1% |

## Honest caveats

- **Precision ≈ 100% is partly a corpus-cleanliness artifact.** In this corpus the fact-bearing source types (evidence/approval/policy/json/table) are exactly the critical spans, and prose is filler — so the safety net separates them cleanly. Real customer context will mix critical and non-critical instances of the same source type, lowering precision. This number will not survive intact on messier data.
- The detector's labels come from **single-ablation** gate effects; jointly-necessary (interaction-only) spans are covered here by the fail-closed structural safety net, not by the learned model.
- Instability and ceilings are pre-economics; prompt-cache-adjusted savings still depend on real cache behaviour (unchanged from the naturalistic study).

## Recommendation — is the compressor now justified?

**The two milestone blockers are cleared on this corpus.** Held-out extractor instability fell to 1.9% (< 10%, all domains), and the fail-closed detector reaches 100.0% recall at 100.0% precision on held-out, lifting the deployable ceiling to 61.1% (≈ the 61.1% oracle ceiling). The previous negative verdict (`EXTRACTOR_NOT_RELIABLE`) no longer holds on this data.

**Recommendation: conditionally proceed — build a NARROW prototype, not a general compressor.** Justified now: a bounded structural + P0-protected context-minimization prototype, since the extractor is reliable and the protected-span detector is high-precision at full recall. NOT yet justified: a general paraphrase-robust compressor sold on these numbers, because (a) the ≈100% precision is partly a corpus-cleanliness artifact, and (b) prompt-cache-adjusted economics still require real customer data. Gate the full build on a `FIELD_REAL` corpus run through these same frozen thresholds.
