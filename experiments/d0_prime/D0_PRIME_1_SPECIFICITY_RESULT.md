# D0_PRIME_1_SPECIFICITY_RESULT — adversarial structural-specificity test (measured)

> STRUCTURAL ONLY — adversarial falsification; burden on Symbol-U. No semantics, no Stage A modification, no new theory. Operators built read-only via the frozen feature_operators constructor; only the feature matrix is replaced by null ensembles. NOT semantic validation, NOT A′, NOT PASS/FAIL/⊥ for Symbol-U semantics. Stage A frozen.

> **DECISION: NOT SPECIFIC**

n_units=14, d=4, null samples K=200 per ensemble. Distinguishable ⇔ ≥1 non-degenerate statistic with two-sided empirical p < 0.0050 (Bonferroni over 10 D0′ statistics). Nulls: A permute-rows, B independent-global, C preserve-norms, D preserve-cosines, E maxent-first-order.

## Stage A reference (exact D0′ statistics)

| statistic | value |
|---|---|
| algebra_dim | 16.0000 |
| commutator_max | 0.9752 |
| commutator_median | 0.5794 |
| commutator_min | 0.1045 |
| n_near_commuting | 0.0000 |
| abelian_defect_max | 0.9904 |
| abelian_defect_mean | 0.5856 |
| trace_order_frac | 0.0000 |
| order_separation_frac | 1.0000 |
| reachability_rank | 4.0000 |

## Null A_permute_rows — INDISTINGUISHABLE

| statistic | stage A | null mean±std | pctl | p(2-sided) | flag |
|---|---|---|---|---|---|
| algebra_dim | 16.0000 | 16.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_max | 0.9752 | 0.9752±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_median | 0.5794 | 0.5794±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_min | 0.1045 | 0.1045±1.388e-17 | 0.0 | 1.0000 | degenerate(const) |
| n_near_commuting | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| abelian_defect_max | 0.9904 | 0.9631±0.0264 | 89.0 | 0.2200 |  |
| abelian_defect_mean | 0.5856 | 0.7571±0.0786 | 2.0 | 0.0400 |  |
| trace_order_frac | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| order_separation_frac | 1.0000 | 1.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| reachability_rank | 4.0000 | 4.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |

- degenerate (null has zero spread — set-invariant under this null, cannot discriminate): algebra_dim, commutator_max, commutator_median, commutator_min, n_near_commuting, trace_order_frac, order_separation_frac, reachability_rank

## Null B_independent_global — INDISTINGUISHABLE

| statistic | stage A | null mean±std | pctl | p(2-sided) | flag |
|---|---|---|---|---|---|
| algebra_dim | 16.0000 | 16.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_max | 0.9752 | 0.9568±0.0287 | 65.0 | 0.7000 |  |
| commutator_median | 0.5794 | 0.6405±0.0502 | 12.5 | 0.2500 |  |
| commutator_min | 0.1045 | 0.0588±0.0489 | 77.0 | 0.4600 |  |
| n_near_commuting | 0.0000 | 0.2650±0.5610 | 0.0 | 1.0000 |  |
| abelian_defect_max | 0.9904 | 0.9512±0.0310 | 95.5 | 0.0900 |  |
| abelian_defect_mean | 0.5856 | 0.7798±0.0538 | 0.5 | 0.0100 |  |
| trace_order_frac | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| order_separation_frac | 1.0000 | 0.9980±0.0041 | 39.5 | 1.0000 |  |
| reachability_rank | 4.0000 | 4.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |

- degenerate (null has zero spread — set-invariant under this null, cannot discriminate): algebra_dim, trace_order_frac, reachability_rank

## Null C_preserve_norms — INDISTINGUISHABLE

| statistic | stage A | null mean±std | pctl | p(2-sided) | flag |
|---|---|---|---|---|---|
| algebra_dim | 16.0000 | 16.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_max | 0.9752 | 0.8922±0.0511 | 99.5 | 0.0100 |  |
| commutator_median | 0.5794 | 0.5591±0.0345 | 70.0 | 0.6000 |  |
| commutator_min | 0.1045 | 0.0752±0.0395 | 78.0 | 0.4400 |  |
| n_near_commuting | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| abelian_defect_max | 0.9904 | 0.9347±0.0341 | 99.5 | 0.0100 |  |
| abelian_defect_mean | 0.5856 | 0.7552±0.0604 | 1.0 | 0.0200 |  |
| trace_order_frac | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| order_separation_frac | 1.0000 | 1.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| reachability_rank | 4.0000 | 4.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |

- degenerate (null has zero spread — set-invariant under this null, cannot discriminate): algebra_dim, n_near_commuting, trace_order_frac, order_separation_frac, reachability_rank

## Null D_preserve_cosines — INDISTINGUISHABLE

| statistic | stage A | null mean±std | pctl | p(2-sided) | flag |
|---|---|---|---|---|---|
| algebra_dim | 16.0000 | 16.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_max | 0.9752 | 0.8595±0.0668 | 99.0 | 0.0200 |  |
| commutator_median | 0.5794 | 0.4547±0.0697 | 97.5 | 0.0500 |  |
| commutator_min | 0.1045 | 0.0564±0.0321 | 89.5 | 0.2100 |  |
| n_near_commuting | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| abelian_defect_max | 0.9904 | 0.9249±0.0563 | 97.5 | 0.0500 |  |
| abelian_defect_mean | 0.5856 | 0.4954±0.0593 | 94.0 | 0.1200 |  |
| trace_order_frac | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| order_separation_frac | 1.0000 | 1.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| reachability_rank | 4.0000 | 4.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |

- degenerate (null has zero spread — set-invariant under this null, cannot discriminate): algebra_dim, n_near_commuting, trace_order_frac, order_separation_frac, reachability_rank

## Null E_maxent_first_order — INDISTINGUISHABLE

| statistic | stage A | null mean±std | pctl | p(2-sided) | flag |
|---|---|---|---|---|---|
| algebra_dim | 16.0000 | 16.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| commutator_max | 0.9752 | 0.9672±0.0184 | 50.5 | 0.9900 |  |
| commutator_median | 0.5794 | 0.6492±0.0654 | 16.0 | 0.3200 |  |
| commutator_min | 0.1045 | 0.0228±0.0310 | 96.5 | 0.0700 |  |
| n_near_commuting | 0.0000 | 0.7000±0.9695 | 0.0 | 1.0000 |  |
| abelian_defect_max | 0.9904 | 0.9485±0.0327 | 95.0 | 0.1000 |  |
| abelian_defect_mean | 0.5856 | 0.7579±0.0704 | 2.0 | 0.0400 |  |
| trace_order_frac | 0.0000 | 0.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |
| order_separation_frac | 1.0000 | 0.9953±0.0066 | 57.5 | 0.8500 |  |
| reachability_rank | 4.0000 | 4.0000±0.0000 | 0.0 | 1.0000 | degenerate(const) |

- degenerate (null has zero spread — set-invariant under this null, cannot discriminate): algebra_dim, trace_order_frac, reachability_rank

## Decision

Stage A is statistically INDISTINGUISHABLE from one or more null ensembles (A_permute_rows, B_independent_global, C_preserve_norms, D_preserve_cosines, E_maxent_first_order). **This is a structural falsification of the specificity of the current feature construction**: comparable non-commutative operator algebra arises under alternative feature assignments, so the structure is not specific to the Symbol-U feature ontology. (Structural only — not a statement about semantics, which remain untested.)

Interpretation guard: this concerns the algebraic structure of the frozen, feature-derived operators only; it is not evidence about meaning and does not validate the operators as the 'true' ones. A NOT-SPECIFIC result falsifies the structural specificity of the feature construction, nothing more.

## Reproducibility metadata

| field | value |
|---|---|
| git_hash | 6e5278de8233860c671e066d648dd6a2c84c9132 |
| python | 3.11.15 |
| platform | Linux-6.18.5-x86_64-with-glibc2.39 |
| numpy | 2.4.6 |
| seed | 70000 |
| runtime_s | 80.199 |

Config:
```json
{
  "K": 200,
  "alpha_bonferroni": 0.005,
  "nulls": [
    "A_permute_rows",
    "B_independent_global",
    "C_preserve_norms",
    "D_preserve_cosines",
    "E_maxent_first_order"
  ]
}
```

| output | sha256 |
|---|---|
| report_body | fdf193693d907c2452bfc1892acedc13437d272eaec6f9fd0b413784b3b9c114 |

> structure, not validated meaning.
