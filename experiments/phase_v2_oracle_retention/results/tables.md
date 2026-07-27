# Phase-v2 oracle-retention — tables

## Pressure n_live=12 (M=8)
| arm | survival | early_surv | acc | acc|surv | acc|evict |
|---|---:|---:|---:|---:|---:|
| C-oracle | 0.847 | 0.870 | 0.825 | 0.967 | 0.040 |
| D-v2 | 0.828 | 0.925 | 0.773 | 0.928 | 0.028 |
| D-zero | 0.813 | 0.828 | 0.785 | 0.949 | 0.079 |
| D-random | 0.788 | 0.819 | 0.738 | 0.928 | 0.040 |
| D-shuffled | 0.817 | 0.847 | 0.775 | 0.941 | 0.038 |

**D-v2 − C:** survival -0.018 ± 0.076; early-survival +0.054; acc -0.052

## Pressure n_live=16 (M=8)
| arm | survival | early_surv | acc | acc|surv | acc|evict |
|---|---:|---:|---:|---:|---:|
| C-oracle | 0.727 | 0.764 | 0.722 | 0.986 | 0.018 |
| D-v2 | 0.735 | 0.793 | 0.662 | 0.891 | 0.026 |
| D-zero | 0.677 | 0.689 | 0.662 | 0.973 | 0.009 |
| D-random | 0.738 | 0.774 | 0.725 | 0.961 | 0.064 |
| D-shuffled | 0.717 | 0.734 | 0.665 | 0.911 | 0.045 |

**D-v2 − C:** survival +0.008 ± 0.041; early-survival +0.029; acc -0.060

