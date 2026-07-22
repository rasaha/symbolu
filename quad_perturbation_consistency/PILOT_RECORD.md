# Pilot Record — Frozen Consistency Coefficient

Frozen **lambda = 0.3**.  Selection rule: highest mean-hard among lambdas that are health-guardrail clean and reach >=0.95 in-distribution on both pilot seeds; chosen to give the method its most favorable fair configuration.

| lambda | mean-hard | delta vs BD-A | min in-dist | all healthy |
|---:|---:|---:|---:|:--:|
| 0.03 | 0.641 | -0.030 | 1.000 | yes |
| 0.1 | 0.671 | -0.000 | 1.000 | yes |
| 0.3 | 0.679 | +0.008 | 1.000 | yes |

BD-A pilot mean-hard: seed 100=0.722, seed 101=0.621

The frozen lambda is used unchanged in the confirmatory multi-seed run.
Even at the most favorable lambda the confirmatory test asks whether BD-Sync significantly beats BD-A; failing that, the null stands.
