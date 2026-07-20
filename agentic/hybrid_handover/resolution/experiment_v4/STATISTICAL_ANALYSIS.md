# STATISTICAL_ANALYSIS — Governance Semantics Experiment v0.1

Paired case-level, hidden pilot (n=60). With only 60 synthetic cases we emphasize
effect size and case-level mechanism over significance.

## Table 5 — fix/break transitions

| comparison | fixes | breaks | unchanged-correct | unchanged-incorrect |
|---|---|---|---|---|
| G4 vs G0 (answered) | 5 | 0 | 4 | 8 |
| G3 vs G0 (answered) | 5 | 0 | 17 | 35 |

## Exact McNemar (full-pipeline answer correctness)

| comparison | fixes | breaks | n discordant | exact p |
|---|---|---|---|---|
| G4 vs G0 | 5 | 0 | 5 | 0.0625 |
| G3 vs G0 | 5 | 0 | 5 | 0.0625 |

## Paired bootstrap (selective accuracy, G4 − G0)

| observed diff | 95% CI | excludes 0 | n | iters | seed |
|---|---|---|---|---|---|
| 0.2312 | [-0.0119, 0.4702] | False | 60 | 10000 | 20240601 |

**Interpretation.** Both G3 and G4 show 5 fixes and 0 breaks (exact McNemar p =
0.0625 — the smallest attainable two-sided p for 5 one-directional discordants, so
significance is bounded by the tiny sample, not by the effect). The G4−G0 selective
bootstrap CI [−0.012, 0.470] includes zero because G4's coverage collapse makes the
answered denominator small and unstable. The clean, coverage-neutral effect is G3's
+0.088 with 5/0 fixes — a real mechanism, modest and pilot-limited in magnitude.
