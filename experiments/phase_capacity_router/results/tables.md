# Phase capacity-router — tables

## single: exact-answer accuracy by arm × regime (3-seed mean)
| arm | N128_K16 | N128_K4 | N128_K8 | N16_K2 | N16_K4 | N16_K8 | N32_K2 | N32_K4 | N32_K8 | N64_K16 | N64_K4 | N64_K8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R-random | 0.125 | 0.030 | 0.063 | 0.143 | 0.262 | 0.508 | 0.073 | 0.135 | 0.265 | 0.245 | 0.053 | 0.122 |
| R-recency | 0.143 | 0.037 | 0.073 | 0.113 | 0.260 | 0.508 | 0.062 | 0.137 | 0.258 | 0.263 | 0.070 | 0.142 |
| R-frequency | 0.048 | 0.012 | 0.018 | 0.183 | 0.382 | 0.673 | 0.083 | 0.152 | 0.292 | 0.185 | 0.042 | 0.090 |
| R-token | 0.110 | 0.017 | 0.055 | 0.128 | 0.253 | 0.500 | 0.070 | 0.122 | 0.237 | 0.263 | 0.082 | 0.138 |
| R-COND | 0.995 | 0.985 | 0.988 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| R-cosine | 0.918 | 0.692 | 0.808 | 0.983 | 0.998 | 1.000 | 0.972 | 0.997 | 1.000 | 1.000 | 0.978 | 1.000 |
| R-bilinear | 0.863 | 0.535 | 0.670 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| R-bilinear-hard | 0.797 | 0.567 | 0.653 | 1.000 | 1.000 | 1.000 | 0.998 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| R-shuffled | 0.175 | 0.065 | 0.097 | 0.190 | 0.343 | 0.532 | 0.127 | 0.162 | 0.292 | 0.300 | 0.140 | 0.180 |
| R-removed | 0.157 | 0.055 | 0.095 | 0.185 | 0.312 | 0.555 | 0.083 | 0.150 | 0.263 | 0.260 | 0.088 | 0.143 |
| R-oracle | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| R-unlimited | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## multihop: exact-answer accuracy by arm × regime (3-seed mean)
| arm | N128_K16 | N128_K4 | N128_K8 | N16_K2 | N16_K4 | N16_K8 | N32_K2 | N32_K4 | N32_K8 | N64_K16 | N64_K4 | N64_K8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R-random | 0.015 | 0.000 | 0.002 | 0.005 | 0.043 | 0.190 | 0.005 | 0.012 | 0.057 | 0.048 | 0.008 | 0.010 |
| R-recency | 0.007 | 0.000 | 0.000 | 0.008 | 0.038 | 0.193 | 0.000 | 0.010 | 0.062 | 0.065 | 0.005 | 0.020 |
| R-frequency | 0.002 | 0.000 | 0.002 | 0.010 | 0.022 | 0.178 | 0.007 | 0.012 | 0.040 | 0.020 | 0.000 | 0.005 |
| R-token | 0.010 | 0.000 | 0.003 | 0.005 | 0.033 | 0.195 | 0.002 | 0.007 | 0.052 | 0.055 | 0.005 | 0.010 |
| R-COND | 0.070 | 0.022 | 0.032 | 0.090 | 0.240 | 0.428 | 0.025 | 0.077 | 0.170 | 0.155 | 0.043 | 0.078 |
| R-cosine | 0.035 | 0.007 | 0.025 | 0.078 | 0.208 | 0.422 | 0.043 | 0.077 | 0.180 | 0.132 | 0.033 | 0.067 |
| R-bilinear | 0.055 | 0.013 | 0.023 | 0.088 | 0.177 | 0.357 | 0.042 | 0.072 | 0.165 | 0.118 | 0.032 | 0.065 |
| R-bilinear-hard | 0.050 | 0.010 | 0.025 | 0.077 | 0.182 | 0.393 | 0.035 | 0.088 | 0.170 | 0.120 | 0.038 | 0.063 |
| R-shuffled | 0.010 | 0.000 | 0.000 | 0.015 | 0.057 | 0.205 | 0.000 | 0.015 | 0.057 | 0.027 | 0.002 | 0.008 |
| R-removed | 0.012 | 0.003 | 0.007 | 0.012 | 0.050 | 0.207 | 0.002 | 0.013 | 0.052 | 0.023 | 0.002 | 0.003 |
| R-oracle | 0.883 | 0.958 | 0.893 | 0.972 | 0.960 | 0.895 | 0.973 | 0.960 | 0.893 | 0.902 | 0.958 | 0.913 |
| R-unlimited | 0.257 | 0.257 | 0.257 | 0.785 | 0.785 | 0.785 | 0.670 | 0.670 | 0.670 | 0.458 | 0.458 | 0.458 |

## Saturation (§11)
Any non-saturated regime with COND in [0.35,0.75]: **False**
- single N16_K2: random 0.143 / COND 1.000 / oracle 1.000 → valid=False
- single N16_K4: random 0.262 / COND 1.000 / oracle 1.000 → valid=False
- single N16_K8: random 0.508 / COND 1.000 / oracle 1.000 → valid=False
- single N32_K2: random 0.073 / COND 1.000 / oracle 1.000 → valid=False
- single N32_K4: random 0.135 / COND 1.000 / oracle 1.000 → valid=False
- single N32_K8: random 0.265 / COND 1.000 / oracle 1.000 → valid=False
- single N64_K4: random 0.053 / COND 1.000 / oracle 1.000 → valid=False
- single N64_K8: random 0.122 / COND 1.000 / oracle 1.000 → valid=False
- single N64_K16: random 0.245 / COND 1.000 / oracle 1.000 → valid=False
- single N128_K4: random 0.030 / COND 0.985 / oracle 1.000 → valid=False
- single N128_K8: random 0.063 / COND 0.988 / oracle 1.000 → valid=False
- single N128_K16: random 0.125 / COND 0.995 / oracle 1.000 → valid=False

## Endpoint Δ (R-bilinear-hard − R-COND), single-hop
- N16_K2: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N16_K4: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N16_K8: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N32_K2: Δacc -0.002, Δadmission -0.002, oracle-gap-closure +0.00
- N32_K4: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N32_K8: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N64_K4: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N64_K8: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N64_K16: Δacc +0.000, Δadmission +0.000, oracle-gap-closure +0.00
- N128_K4: Δacc -0.418, Δadmission -0.418, oracle-gap-closure -27.89
- N128_K8: Δacc -0.335, Δadmission -0.335, oracle-gap-closure -28.71
- N128_K16: Δacc -0.198, Δadmission -0.198, oracle-gap-closure -39.67

## Causal controls (best matcher, multihop N128 K8)
intact 0.025 / summary_removed 0.007 / summary_shuffled 0.000 / score_shuffled 0.002 / causal_delta +0.017

## Multi-hop breakdown (N128 K8)
| arm | acc | P(all req admitted) | acc|all-admitted |
|---|---:|---:|---:|
| R-random | 0.002 | 0.002 | 0.333 |
| R-COND | 0.032 | 0.092 | 0.353 |
| R-bilinear-hard | 0.025 | 0.047 | 0.469 |
| R-oracle | 0.893 | 1.000 | 0.893 |
