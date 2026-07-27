# Phase v3 selective-SSM — tables

## Focus Top-1 by variant × distance (mode B_annealed, mean over seeds)
| variant | d64 | d128 | d256 | d512 | d1024 | d2048 | d4096 |
|---|---|---|---|---|---|---|---|
| V1 | 0.911 | 0.993 | 0.998 | 0.828 | 0.658 | 0.548 | 0.474 |
| V2-S | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.938 |
| V3-B | 1.000 | 1.000 | 1.000 | 1.000 | 0.999 | 0.544 | — |
| V3-AB | 0.995 | 0.952 | 0.819 | 0.609 | 0.438 | 0.383 | — |
| V3-ABC | 0.999 | 0.998 | 0.958 | 0.792 | 0.433 | 0.318 | 0.378 |

## Control separation (V3-ABC state − max(shuffled,random))
- d512: state 0.792 − control 0.068 = **+0.723** (gate MET); V3−V1 -0.037
- d1024: state 0.433 − control 0.069 = **+0.364** (gate MET); V3−V1 -0.225
- d2048: state 0.318 − control 0.078 = **+0.240** (gate MET); V3−V1 -0.229

## Annealed retention (d2048): B/A = 1.65 (MET ≥0.80)
