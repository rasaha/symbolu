# STRUCTURAL_V1 — Stage A Structural Report

> **structure, not validated meaning.** This report establishes structural signal
> only. It does NOT validate meaning, Sanskrit/varna privilege, or LLM
> usefulness. Operators are provisional (feature-derived, not estimated).

## Verdict: **FAIL**

Stage A PASS = G1 AND G2 AND G3 AND G4.

## Gates

| gate | result | key numbers |
|---|---|---|
| G1_order_sensitivity | PASS | mean_standardized_order_effect=1.1242, bag_order_effect=0.0000, threshold=0.1000 |
| G2_beats_random_orthogonal | PASS | real_structure_score=0.5987, null_p95=0.0104, null_mean=-0.0993 |
| G3_beats_relabel | PASS | real_structure_score=0.5987, null_p95=0.0971, null_mean=-0.0748 |
| G4_factorization | FAIL | sub_low_dim=1.0000, sub_gap_reliable=0.0000, sub_beats_randfactor=1.0000, effective_rank=3.6838, effective_rank_max=6.0000, commuting_coef_mean_abs=0.4381, coupling_coef_mean_abs=0.6823, gap_ci_low=-0.0181, randfactor_null_p95=0.0339, real_structure_score=0.5987 |

### Gate notes
- **G1_order_sensitivity** — bag order-effect is identically 0 (additive aggregation).
- **G2_beats_random_orthogonal** — discriminator is STRUCTURE; random operators may have larger magnitude.
- **G3_beats_relabel** — tests that the SPECIFIC feature->unit binding matters.
- **G4_factorization** — partly circular by construction (operators built from features); informative parts are the relabel/random-factorization nulls.

## Diagnostics

- n_units: 14.0000
- n_pairs: 91.0000
- real_structure_score: 0.5987
- structure_score_std_over_seeds: 0.0228
- mean_order_effect: 1.1242
- effective_rank: 3.6838

## Warnings

- none

## Interpretation (bounded)

No qualifying structural signal: gate(s) G4_factorization failed. The feature-grounded operator product did not produce inventory-specific, factorizable order-structure beyond the nulls. This is a structural-null result; it says nothing for or against meaning, varna privilege, or LLM usefulness, none of which Stage A tests. structure, not validated meaning.
