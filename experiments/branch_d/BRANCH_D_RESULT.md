# BRANCH_D_RESULT — phoneme-identity semantic upper bound (measured)

> Reachable-data semantic measurement; UPPER-BOUND / necessary-condition test on the LINEAR/additive model class. **Not Symbol-U validation, not A′ PASS/FAIL/⊥.** It can only falsify or bound a phoneme-level essence effect. A′ remains halted; Stage A untouched; no L2 F; no decoders. Y = Warriner VAD (academic norms; not redistributed).

> **DECISION: UPPER_BOUND_POSITIVE**

## Datasets & join

- E (phoneme identity): CMUdict v0.7b ARPABET, stress-stripped (BSD-2).
- Phonology: PanPhon articulatory features via frozen ARPABET→IPA map (MIT).
- Y: Warriner et al. (2013) VAD means (academic norms; local only, not committed).
- joined N = 13383 words (Warriner 13905 ∩ CMUdict 126052); N_eff floor 800 → met.
- uncovered phonemes: none.
- features: PHON = 26 (mean articulatory + n_phonemes + n_syllables); E_max = 39 phoneme-identity counts. NUIS=length included in PHON; frequency omitted (not in Warriner/CMUdict).

## Incremental predictive test  (Y ~ PHON  vs  Y ~ PHON + E_max)

| endpoint | R²(PHON) | R²(PHON+E_max) | ΔR² | partial r | perm-null p95 | perm p |
|---|---|---|---|---|---|---|
| valence | 0.0020 | 0.0087 | 0.0067 | 0.082 | -0.0020 | 0.00498 |
| arousal | 0.0214 | 0.0226 | 0.0011 | 0.034 | -0.0020 | 0.00498 |
| dominance | 0.0023 | 0.0097 | 0.0074 | 0.086 | -0.0020 | 0.00498 |

## Controls

- random-E control (valence): ΔR² = -0.0032, partial r = 0.000, p = 0.378 (should be ≈ 0 / non-significant).
- relabel/column-permutation of phoneme identities: a linear-probe column permutation → R² invariant by construction (degenerate; reported transparently, as in D₀′.1).
- primary null = row-permutation of E_max vs (Y, PHON), K=200.

## Interpretation

**A necessary condition survives (MARGINAL: 0.05 ≤ partial r < 0.10): phoneme identity contains residual information about Y (valence partial r = 0.082) beyond articulatory phonology.** This does NOT validate Symbol-U; it only means a specific E table is still worth testing, with this value as its upper bound. Caveat: the bound also absorbs morphological/etymological systematicity, so it OVER-estimates any purely sound-symbolic essence effect (a conservative upper bound).

Model-class caveat: linear ridge on additively-aggregated counts; the DPI upper bound holds for linear/additive essence aggregations (the pre-registered A1.4 branch). English lexicon testbed; not a Sanskrit-privilege claim.

## Reproducibility metadata

| field | value |
|---|---|
| git_hash | 4c0ee552832ab2d37d271ece7a7dc734fa6c39dc |
| python | 3.11.15 |
| platform | Linux-6.18.5-x86_64-with-glibc2.39 |
| numpy | 2.4.6 |
| seed | 13 |
| runtime_s | 58.34 |

Config:
```json
{
  "K_perm": 200,
  "min_partial_r": 0.1,
  "n_eff_floor": 800,
  "endpoints": [
    "valence",
    "arousal",
    "dominance"
  ],
  "data_dir": "/tmp/claude-0/-home-user-symbolu/e6c5059c-bd37-54fe-a8ea-d7b7bc12b135/scratchpad/branchD"
}
```

| output | sha256 |
|---|---|
| report_body | 4c4ca7b25e958d3b4f2cae4c8f2650fa2c1b1e0e78bcb139c724ce644d31f9d0 |

> structure, not validated meaning.
