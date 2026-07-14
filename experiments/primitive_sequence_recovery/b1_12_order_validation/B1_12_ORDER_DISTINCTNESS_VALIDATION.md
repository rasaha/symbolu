# B1.12 V1.2 Order-Distinctness — Validation (descriptive only)

**Validation artifact only.** No frozen artifact, threshold, candidate-selection rule, parser,
or experiment output was changed. This document describes the behaviour of the newly frozen
V1.2 order-distinctness definition over the **complete candidate pool**. No search,
optimization, tuning, threshold adjustment, subset reselection, or candidate ranking was
performed.

## Frozen definition (used verbatim)
```
d_ord|inv(x, y) = max(0, Lev(x, y) - Lev(sort(x), sort(y))) / max(|x|, |y|)
```
where `x`, `y` are a candidate's ordered consonant sequence (`cons_seq`). The per-word self
metric `d_ord|inv(x, sort(x))` is the previous V1.1 self-order measure (verified in §4).

## Candidate pool
- Source: `native_gate_g0/candidate_inventory.json` — the complete eligible candidate pool.
- **N = 107 candidates**; `x` = the ordered consonant sequence per candidate.
- Pairwise basis: unique unordered off-diagonal pairs = C(107, 2) = **5 671 pairs**. The
  metric is symmetric (`Lev` and `sort` are), and the diagonal `d_ord|inv(x, x) = 0` by
  construction, so it is excluded from the descriptive statistics.

## 1–2. Pairwise matrix + descriptive statistics
Computed over all 5 671 pairs (full matrix in `pairwise_order_statistics.json`;
per-bin counts in `pairwise_order_histogram.csv`).

| statistic | value |
|---|---|
| min | 0.0 |
| max | 1.0 |
| mean | 0.0368 |
| median | 0.0 |
| Q1 (25%) | 0.0 |
| Q2 (50%) | 0.0 |
| Q3 (75%) | 0.0 |
| % exactly 0 | **89.74%** |
| % > 0 | 10.26% |
| % > 0.25 | 8.22% |
| % > 0.5 | 0.49% |
| % > 0.75 | 0.05% |

Histogram (non-empty bins; width 0.05):

| bin | count | fraction |
|---|---|---|
| [0.00, 0.05) | 5089 | 0.8974 |
| [0.20, 0.25) | 116 | 0.0205 |
| [0.30, 0.35) | 355 | 0.0626 |
| [0.45, 0.50) | 83 | 0.0146 |
| [0.65, 0.70) | 25 | 0.0044 |
| [0.95, 1.00) | 3 | 0.0005 |

The distribution is heavily zero-concentrated with a few discrete clusters. The clustering at
≈0.25, 0.333, 0.5, 1.0 is a direct consequence of the metric being an integer numerator
(`Lev(x,y) − Lev(sort(x),sort(y))`) over a small denominator (`max(|x|,|y|) ∈ {2,3,4}` for this
pool).

## 3. What kinds of pairs produce which scores
- **Zero scores (89.74%).** Pairs where the ordering explains none of the edit distance, i.e.
  `Lev(x,y) ≤ Lev(sort(x),sort(y))`. This dominates because most candidate pairs differ chiefly
  in their consonant **inventory** (different symbols), so sorting does not shrink their
  distance; and for many short, distinct-consonant sequences already in sorted order the
  order term is trivially 0.
- **Moderate scores (≈0.25–0.5).** Pairs that share part of their inventory and whose edit
  distance is partly attributable to ordering. The discrete values (1/4, 1/3, 1/2) come from
  one or two order-driven edits over a length-2/3/4 denominator.
- **High scores (>0.75, up to 1.0).** Anagram-like pairs whose consonant **multiset is (nearly)
  identical** and which therefore differ almost entirely by ORDER. The extreme (d_ord = 1.0)
  is a two-consonant pair with the same multiset in swapped order.

## 4. Mathematical verification: self metric ≡ V1.1
For any candidate `x`, substitute `y = sort(x)` into the frozen V1.2 formula:
```
d_ord|inv(x, sort(x))
  = max(0, Lev(x, sort(x)) - Lev(sort(x), sort(sort(x)))) / max(|x|, |sort(x)|)
```
Because `sort` is idempotent, `sort(sort(x)) = sort(x)`, hence `Lev(sort(x), sort(sort(x))) =
Lev(sort(x), sort(x)) = 0`. Sorting permutes symbols so `|sort(x)| = |x|`. And `Lev ≥ 0`, so the
outer `max(0, ·)` is the identity. Therefore
```
d_ord|inv(x, sort(x)) = Lev(x, sort(x)) / |x|,
```
which is **exactly** the previous V1.1 self-order measure. ∎

Numerically confirmed for **all 107 candidates** (exact equality, tolerance 1e‑12):
`self_metric_equality.all_candidates_equal = true`.

## 5. Frozen G0 constants and selected subset — unchanged
Read-only confirmation (no `build()` was run):

| item | value | unchanged |
|---|---|---|
| K | 6 | ✓ (module == report == pinned) |
| MAX_JACCARD_CAP | 0.34 | ✓ |
| MEAN_JACCARD_CAP | 0.20 | ✓ |
| POOL_SIZE | 20 | ✓ |
| cons_len_range | [2, 4] | ✓ |
| core pool size | 20 | ✓ |
| eligible candidates | 107 | ✓ |
| **selected subset** | `aśva, bala, bhaya, duḥkha, gaja, megha` | ✓ (matches frozen manifest & report) |

The live `b1_native_gate_g0` module constants equal the frozen report constants and the pinned
values; the selected subset in `selected_set_manifest.json` matches the frozen report.

## 6. Descriptive correlations (NOT used for tuning)
Over the 5 671 pairs (Pearson / Spearman), descriptive only:

| vs | Pearson | Spearman |
|---|---|---|
| edit distance `Lev(x,y)` | 0.088 | 0.125 |
| inventory overlap (Jaccard of consonant sets) | **0.477** | 0.460 |
| length difference | −0.059 | −0.030 |

Order-distinctness is moderately, positively associated with **inventory overlap** (pairs that
share more of their inventory have more room to differ by order alone), weakly associated with
raw edit distance, and essentially uncorrelated with length difference. These are reported as
descriptions of the metric's behaviour; **no threshold was optimized against them.**

## 7. Anonymous illustrative examples
Anonymous IDs only (no spelling/identity revealed). Illustrative — **not** labelled good or bad.

| example | pair | d_ord | edit dist | inventory overlap | len diff | same inventory | repeated |
|---|---|---|---|---|---|---|---|
| highest scoring | C002–C074 | 1.000 | 2 | 1.00 | 0 | yes | no |
| lowest non-zero | C001–C079 | 0.250 | 3 | 0.40 | 1 | no | no |
| repeated-symbol | C003–C102 | 0.333 | 3 | 0.25 | 0 | no | yes |
| inventory-different, order-identical | C000–C001 | 0.000 | 3 | 0.00 | 1 | no | no |
| same inventory, maximally reordered | C002–C074 | 1.000 | 2 | 1.00 | 0 | yes | no |

Notes: the highest-scoring pair and the same-inventory-maximally-reordered pair coincide — a
two-consonant pair with an identical multiset in swapped order (d_ord = 1.0). The
inventory-different/order-identical pair has zero inventory overlap, so its distance is entirely
inventory-driven and the order term contributes nothing (d_ord = 0). The repeated-symbol pair
involves a candidate whose sequence contains a repeated consonant (n_tokens 3, n_distinct 2).

## 8. No-optimization attestation
This validation performed **none** of the following: search, optimization, tuning, threshold
adjustment, subset reselection, or candidate ranking. It read the frozen candidate inventory and
G0 report/manifest and wrote **only** the three new validation artifacts:
`B1_12_ORDER_DISTINCTNESS_VALIDATION.md`, `pairwise_order_statistics.json`,
`pairwise_order_histogram.csv` (+ the generating script). No frozen artifact, threshold,
candidate selection, parser, or experiment conclusion was changed.

## Deliverables
- `B1_12_ORDER_DISTINCTNESS_VALIDATION.md` (this file)
- `pairwise_order_statistics.json`
- `pairwise_order_histogram.csv`
- `validate_b1_12_order_distinctness.py` (reproducible generator; read-only over frozen inputs)
