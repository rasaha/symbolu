# Statistics Report — Tables 5–7

Paired case-level statistics, Hybrid vs GraphTraversal, hidden pilot (n=60).

## Table 5 — Exact McNemar per stage

| stage (binary correctness) | hybrid fixes | hybrid breaks | discordant n | exact p |
|---|---|---|---|---|
| discovery_complete | 18 | 1 | 19 | 0.0001 |
| governanceG | 0 | 0 | 0 | 1.0000 |
| packetP | 0 | 0 | 0 | 1.0000 |
| answer_correct | 0 | 0 | 0 | 1.0000 |

Discovery completeness improves overwhelmingly (18 cases fixed, 1 broken,
exact two-sided p = 7.6e-05). Governance, packet, and answer correctness are
perfectly concordant (n=0 discordant) because the hybrid reuses the frozen
governance + packet builder unchanged — the discovery layer is the only moving
part, exactly as designed.

## Table 6 — Paired bootstrap on the macro

| observed diff | 95% CI | excludes 0 | n | iters | seed |
|---|---|---|---|---|---|
| 0.0788 | [0.0350, 0.1311] | yes | 60 | 10000 | 20240601 |

## Table 7 — Holm correction over the stage McNemar family

| stage | raw p | Holm threshold | Holm-adj p | reject null |
|---|---|---|---|---|
| discovery_complete | 0.0001 | 0.0125 | 0.0003 | yes |
| governanceG | 1.0000 | 0.0167 | 1.0000 | no |
| packetP | 1.0000 | 0.0250 | 1.0000 | no |
| answer_correct | 1.0000 | 0.0500 | 1.0000 | no |

Only the discovery-completeness endpoint survives Holm correction, and it does so
decisively. Significance is reported; it is not conflated with practical
significance or with non-inferiority.
