# Matcher study — focus↔event relevance (V2-S recurrence unchanged, γ=1, ω=0)

## 1. Pilot (2 seeds) — candidate selection

| arm | AUROC | rel−distr margin | d2048 | d4096 | focus-removed margin | top10 prec | top10 recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| token | 0.498 | −0.002 | 0.889 | 0.751 | −0.002 | 0.389 | 0.100 |
| COND-MLP (frozen baseline) | 0.620 | +0.106 | 1.000 | 1.000 | +0.001 | 0.730 | 0.187 |
| cosine | 0.796 | +5.846 | 0.990 | 0.981 | −0.147 | 0.872 | 0.223 |
| bilinear | 0.830 | +48.827 | 0.996 | 0.994 | +0.359 | 0.865 | 0.222 |
| bilinear+hard | **0.837** | +40.910 | 0.995 | 0.996 | +0.574 | 0.842 | 0.228 |

Selected candidate by hard-negative-AUROC priority: **bilinear+hard** (0.837, most stable
0.845/0.828). (The 2-seed *focus-removed margin* for bilinear looked like a shortcut, +0.36/+0.57,
but that is an artifact of the raw-margin metric under a degenerate constant summary — the
confirmation's AUROC-based controls resolve it decisively below.)

## 2. Confirmation (3 seeds, hard-negative dataset)

| arm | AUROC | hard AUROC | win-rate | rel−hard margin | d2048 state | d4096 state | d2048 readout | wr rel/ord/hard/fill |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| token | 0.502 | 0.502 | 0.502 | +0.001 | 0.912 | 0.737 | 0.790 | 0.60/0.60/0.60/0.33 |
| COND-MLP | 0.607 | 0.608 | 0.608 | +0.082 | **1.000** | **1.000** | 1.000 | 0.08/0.00/0.00/0.00 |
| bilinear+hard | **0.803** | **0.804** | **0.804** | +39.851 | 0.986 | 0.988 | 0.988 | 0.77/0.39/0.39/0.10 |

Per-seed bilinear+hard AUROC 0.845 / 0.829 / 0.736 (min 0.736 ≥ 0.70); d4096 state 0.993 / 1.000 / 0.970.

### Causal summary controls (bilinear+hard hard-AUROC under intervention)

| control | hard AUROC |
|---|---:|
| intact | 0.804 |
| focus summary removed | 0.508 |
| focus summary shuffled | 0.518 |
| random focus summary | 0.493 |

**causal_delta = intact − mean(removed, shuffled, random) = 0.804 − 0.506 = +0.298.**
The advantage collapses to chance without the correct focus summary → the matcher performs
genuine focus-event matching, **not** a focus-independent shortcut.

## 3. Promotion decision (§7)

| criterion | result |
|---|---|
| 1. overall AUROC ≥ 0.70 (every seed) | ✅ (min 0.736) |
| 2. hard-negative AUROC ≥ 0.65 | ✅ (min 0.738) |
| 3. rel−hard margin positive every seed | ✅ |
| 4. paired win-rate ≥ 0.70 | ✅ (min 0.738) |
| 5. relevant write rate > hard write rate | ✅ (0.77 vs 0.39) |
| 6. hard false-write improves over COND-MLP | ❌ (0.39 vs COND-MLP 0.00) |
| 7. d4096 decode no worse than COND-MLP | ❌ (0.988 vs 1.000) |
| 8. controls eliminate the advantage | ✅ (causal_delta +0.298) |
| 10. recurrence / O(N) unchanged | ✅ |

**Promotion: NO.** The matcher solves the *discrimination* bottleneck causally (AUROC
0.62 → 0.80, causal_delta +0.30, clean write separation) but does **not** improve the
downstream memory decode (0.988 vs COND-MLP 1.000) or write economy — because the task is
already saturated (COND-MLP decodes perfectly by writing essentially only the cue). Since
bilinear+hard **passed** the causal controls, the cosine fallback was not required (§4).
