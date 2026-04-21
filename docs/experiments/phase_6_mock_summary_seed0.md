# Phase 6 Summary — §1.10 three-decoder comparison

**Benchmark:** `mock`   **Seed:** `0`   **N:** `48`


## Per-decoder results

| Decoder | Accuracy | Mean latency (s) | Median latency (s) |
|---|---|---|---|
| vanilla | 33.33% | 0.59 ms | 0.57 ms |
| conventional_blend | 100.00% | 0.75 ms | 0.72 ms |
| bcvf_trust | 100.00% | 2.97 ms | 2.91 ms |

## §1.10 classification (single seed)

**Classification:** `NULL`

- BCVF-trust accuracy: 100.00%
- Conventional-blend accuracy: 100.00%
- Δ (trust − blend): +0.00 pp
- Latency ratio: 3.96×
- McNemar paired: b=0, c=0, p=1.000

**Notes:** |trust − blend| = 0.00 pp < 0.5 pp. §1.10 null — structural claim does not transfer.


## Paired comparisons (McNemar)

| A | B | b (A✓ B✗) | c (A✗ B✓) | p (exact two-sided) |
|---|---|---|---|---|
| vanilla | conventional_blend | 0 | 32 | 0.000 |
| vanilla | bcvf_trust | 0 | 32 | 0.000 |
| conventional_blend | bcvf_trust | 0 | 0 | 1.000 |
