# BRANCH_D1_RESULT — robustness & confound analysis (measured)

> Robustness of the Branch D phoneme-identity upper bound under morphology/length deconfounding and rime-grouped leakage-controlled CV. **Not Symbol-U validation, not A′ PASS/FAIL/⊥.** A′ halted; Stage A untouched; linear/additive model class; English lexicon. Y = Warriner VAD (academic norms; not redistributed).

> **DECISION: UPPER_BOUND_NULL_AFTER_CONTROLS**

## Setup

- joined N = 13383; rime groups = 531 (leakage-controlled CV).
- DECONF baseline adds n_letters + 37 suffix/prefix morphology indicators to the 26-dim PHON baseline.
- duplicate pronunciations: first CMUdict entry per word (variants skipped).
- frequency (SUBTLEX) & concreteness (Brysbaert): not reachable on quick GitHub probe → omitted (stated).
- primary null: row-permutation of E_max, K=200; grouped tests use rime-disjoint folds.

## Endpoint: valence

| condition | R²(base) | R²(base+E_max) | ΔR² | partial r | perm p | survives |
|---|---|---|---|---|---|---|
| original (PHON, random CV) = Branch D | 0.0020 | 0.0087 | 0.0067 | 0.082 | 0.00498 | yes |
| deconfounded (PHON+morph+length, random CV) | 0.0349 | 0.0371 | 0.0023 | 0.048 | 0.00498 | no |
| rime-grouped CV (PHON) | -0.0004 | 0.0009 | 0.0013 | 0.036 | 0.00498 | no |
| deconfounded + rime-grouped (decisive) | -0.0079 | -0.0108 | -0.0029 | 0.000 | 0.299 | no |

## Endpoint: arousal

| condition | R²(base) | R²(base+E_max) | ΔR² | partial r | perm p | survives |
|---|---|---|---|---|---|---|
| original (PHON, random CV) = Branch D | 0.0214 | 0.0226 | 0.0011 | 0.034 | 0.00498 | no |
| deconfounded (PHON+morph+length, random CV) | 0.0280 | 0.0287 | 0.0007 | 0.027 | 0.00498 | no |
| rime-grouped CV (PHON) | 0.0186 | 0.0159 | -0.0027 | 0.000 | 0.159 | no |
| deconfounded + rime-grouped (decisive) | 0.0108 | 0.0106 | -0.0002 | 0.000 | 0.00498 | no |

## Endpoint: dominance

| condition | R²(base) | R²(base+E_max) | ΔR² | partial r | perm p | survives |
|---|---|---|---|---|---|---|
| original (PHON, random CV) = Branch D | 0.0023 | 0.0097 | 0.0074 | 0.086 | 0.00498 | yes |
| deconfounded (PHON+morph+length, random CV) | 0.0286 | 0.0313 | 0.0027 | 0.053 | 0.00498 | yes |
| rime-grouped CV (PHON) | -0.0019 | 0.0004 | 0.0023 | 0.048 | 0.00498 | no |
| deconfounded + rime-grouped (decisive) | -0.0041 | -0.0040 | 0.0001 | 0.010 | 0.0199 | no |

## Decision & interpretation

After morphology/length controls and rime-grouped CV, phoneme identity adds no significant information about valence beyond phonology. The Branch D positive does not survive obvious confounds: no deterministic phoneme-level essence table can improve prediction here once lexical confounds are removed (this dataset, linear model class).

Caveat: morphology proxies are orthographic and coarse; rime grouping controls rhyme-family leakage, not all etymological structure; frequency/concreteness not included. Conclusions hold for the linear/additive model class and the English testbed.

## Reproducibility metadata

| field | value |
|---|---|
| git_hash | 89116201102072aef63e76e309b4722e29168f12 |
| python | 3.11.15 |
| platform | Linux-6.18.5-x86_64-with-glibc2.39 |
| numpy | 2.4.6 |
| seed | 13 |
| runtime_s | 256.613 |

Config:
```json
{
  "K_perm": 200,
  "n_eff_floor": 800,
  "endpoints": [
    "valence",
    "arousal",
    "dominance"
  ],
  "deconf_dims": 64,
  "n_rime_groups": 531
}
```

| output | sha256 |
|---|---|
| report_body | f1df55ad0b515ccf6870617790d9aced0d0d0285198591a04c52f7c78cdce69b |

> structure, not validated meaning.
