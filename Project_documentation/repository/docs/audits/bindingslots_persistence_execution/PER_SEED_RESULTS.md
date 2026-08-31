# Per-seed results

needle@d96 (chance ≈ 0.02); correct-slot prob at step 600 → 1200; randomized-address (from the
post-train baseline); ppl@256 vs same-seed A+ (gate = ≤ 1.20×A+). Categories are the frozen
per-seed classifier output. A+ ×5 are window-only controls (needle ≈ 0), used only as the same-seed
causal/quality reference.

## R0 (frozen CR1 baseline) — clean-stable 2/5
| seed | needle | prob 600→1200 | rand-addr | ppl/A+ | category |
|---|---|---|---|---|---|
| 23 | 0.00 | 1.00→0.94 | 0.00 | 127/134 | FORMED_THEN_COLLAPSED |
| 24 | 1.00 | 1.00→0.94 | 0.02 | 147/123 | **CLEAN_STABLE** |
| 25 | 0.12 | 1.00→0.81 | 0.03 | 140/115 | QUALITY_FAILED |
| 26 | 1.00 | 1.00→0.72 | 0.01 | 124/151 | FORMED_THEN_COLLAPSED |
| 27 | 0.98 | 0.99→0.77 | 0.00 | 141/132 | **CLEAN_STABLE** |

## O1R (standing residual λ=0.01, 601–1200) — futile, 1 clean
| 23 | 1.00 | 0.97→0.78 | 0.00 | 132/134 | **CLEAN_STABLE** |
| 24 | 1.00 | 0.56→0.55 | **1.00** | 153/123 | QUALITY_FAILED |
| 25 | 1.00 | 0.75→0.82 | 0.00 | 155/115 | QUALITY_FAILED |

Routing retained on 23/25 (prob 0.78/0.82, rand-addr collapses) — residual fixes the routing decay —
but quality regresses on 24/25.

## H1 (0.1× LR on addressing group, 600–900) — futile, 1 clean
| 23 | 1.00 | 1.00→0.84 | 0.01 | 109/134 | **CLEAN_STABLE** |
| 24 | 0.94 | 1.00→0.97 | **0.21** | 140/123 | FORMED_AND_RETAINED_BUT_CAUSALLY_UNCLEAN |
| 25 | 1.00 | 1.00→0.99 | 0.02 | 141/115 | QUALITY_FAILED |

## H2 (functional teacher, step-600 slot-read distribution) — futile, 1 clean
| 23 | **0.00** | 1.00→**0.96** | 0.05 (base 0.00) | 155/134 | FORMED_THEN_COLLAPSED |
| 24 | 0.28 | 1.00→0.95 | 0.00 | 136/123 | **CLEAN_STABLE** (weak; see below) |
| 25 | 0.61 | 1.00→0.97 | 0.00 | 146/115 | QUALITY_FAILED |

## O1 (diagnostic, NOT selectable) — reference phenotype, 1 clean
| 23 | 1.00 | 0.97→0.73 | 0.00 | 134/134 | CLEAN_STABLE |
| 24 | 1.00 | 0.56→**0.17** | **1.00** | 148/123 | causally-unclean |
| 25 | 1.00 | 0.75→0.54 | 0.03 | 145/115 | QUALITY_FAILED |
| 26 | 1.00 | 0.77→**0.23** | 0.25 | 142/151 | causally-unclean |
| 27 | 1.00 | 0.61→**0.25** | **1.00** | 129/132 | causally-unclean |

O1 reproduces the functional-routing phenotype on the reserved seeds: reliable needle formation with
**routing decay after withdrawal** (prob → 0.17–0.25) and address-independent survival (rand-addr up
to 1.0) on 4/5 seeds.

## H2 seed24 weak-but-clean audit (explicit arithmetic)

- forming: needle 0.283 ≥ 0.075 ✓; 0.283 − A+ 0.033 = 0.250 ≥ 0.050 ✓; 0.283 ≥ 0.07 ✓
- routing: prob 0.948 ≥ 0.50 ✓; rank ≤ 5 ✓; margin ≥ 3.0 ✓
- causal: randomized-address 0.00 from baseline 0.283 (meaningful collapse) ✓; slots-off collapses ✓
- distance: d16 0.358 ≥ A+ 0.033 ✓; d220 0.175 > A+ 0.017 ✓
- quality: ppl 135.7 ≤ 1.20 × A+ 123.2 = 147.8 ✓

→ `CLEAN_STABLE` is valid under the frozen rule. It is a genuinely **weak** former (0.283); flagged so
the label does not read as inconsistent.
