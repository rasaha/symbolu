# §15.11 Phase 2 — Layer-wise phase-coherence probe (result)

_Schema version: `15.11`._  
_Model: `Qwen/Qwen2.5-7B-Instruct`; layers used: 29 (embedding + 28 transformer); hidden dim: `3584`; FFT bins used: W=1791 of 1793 (DC and Nyquist excluded); prompt format: `Q: {question}\nA:`._

## Cascade verdict (mechanical readout)

**Label:** `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`

**Rationale:** NO_MATERIAL (direction gate): wrong-direction failure on at least one benchmark. BCVF-faithful direction (higher F predicts correct) did not hold. (HaluEval=0.461 < 0.5; TruthfulQA-MC=0.485 < 0.5).

| benchmark | phase AUC | §13.10 baseline | ΔAUC vs §13.10 | §15.10 supervised | ΔAUC vs §15.10 | direction held |
|---|---|---|---|---|---|---|
| HaluEval-QA | 0.461 | 0.661 | -0.200 | 0.669 | -0.208 | no |
| TruthfulQA-MC | 0.485 | 0.661 | -0.176 | 0.622 | -0.137 | no |

## Probe details — HaluEval-QA

- N questions: 100 (correct: 30, wrong: 70)
- π observed: 0.300 (pinned: 0.300)
- Phase-coherence AUC: **0.461** (§13.10 baseline: 0.661; ΔAUC vs §13.10: -0.200)
- §15.10 supervised AUC (disclosure): 0.669 (ΔAUC vs §15.10: -0.208)
- Direction held (AUC ≥ 0.5): **no**
- Coherence matrix summary (over 406 off-diagonal entries × 100 questions):
  - off-diagonal min:  -0.0449
  - off-diagonal mean: +0.4232
  - off-diagonal max:  +0.9369
  - off-diagonal std:  0.2283

**Selective-prediction operating points (disclosure only):**

| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |
|---|----|-----|----------|------------|------------|----------|
| 0.40 | — | 0.000 | 0.000 | — | 0 | no |
| 0.50 | — | 0.000 | 0.000 | — | 0 | no |
| 0.75 | — | 0.000 | 0.000 | — | 0 | no |

## Probe details — TruthfulQA-MC

- N questions: 100 (correct: 25, wrong: 75)
- π observed: 0.250 (pinned: 0.250)
- Phase-coherence AUC: **0.485** (§13.10 baseline: 0.661; ΔAUC vs §13.10: -0.176)
- §15.10 supervised AUC (disclosure): 0.622 (ΔAUC vs §15.10: -0.137)
- Direction held (AUC ≥ 0.5): **no**
- Coherence matrix summary (over 406 off-diagonal entries × 100 questions):
  - off-diagonal min:  -0.0275
  - off-diagonal mean: +0.4325
  - off-diagonal max:  +0.9510
  - off-diagonal std:  0.2271

**Selective-prediction operating points (disclosure only):**

| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |
|---|----|-----|----------|------------|------------|----------|
| 0.35 | 0.4541 | 0.110 | 0.110 | 0.364 | 11 | yes |
| 0.50 | — | 0.000 | 0.000 | — | 0 | no |
| 0.75 | — | 0.000 | 0.000 | — | 0 | no |

## Pinned configuration (§15.11 §0.8-binding)

- **Model:** `Qwen/Qwen2.5-7B-Instruct`; all 29 per-layer last-token hidden states (embedding + 28 transformer layers).
- **Prompt format:** `Q: {question}\nA:` (matches §15.10 PROMPT_FORMAT).
- **FFT:** `numpy.fft.rfft` along hidden dim (N=3584 → 1793 complex bins); used bins k ∈ [1, 1791] (W=1791; excludes DC k=0 and Nyquist k=1792).
- **Windowing:** rectangular (none).
- **Detrending:** none.
- **Coherence formula:** C[i, j] = (1/W) · Σ_k cos(φ_i[k] − φ_j[k]).
- **Feature aggregation:** mean over upper-triangular off-diagonal of 29x29 C (406 entries).
- **Direction convention:** higher F predicts correct (BCVF-faithful).
- **Cascade thresholds:** STRONG AUC≥0.75 AND ΔAUC≥+0.05 (both benchmarks); PARTIAL AUC≥0.66 AND ΔAUC>0 (at least one); otherwise NO_MATERIAL. Direction gate: AUC<0.5 on either benchmark → NO_MATERIAL automatic.
- **Selective-prediction floor:** N_MIN=10; primary alpha = 0.5.

## Caveats (§0.8-disclosed)

- **Single mechanism within the phase-coherence class.** This tests ONE phase-coherence formula: layer-wise, mean off-diagonal, BCVF-faithful direction. A negative result rules out THIS instantiation; sample-wise (multi-decode), paraphrase-wise (multi-prompt), and alternative aggregations remain untested but known.
- **Layer-wise was selected over sample-wise / paraphrase-wise** for cost (single forward pass per question) and BCVF-analog cleanness (layers as N streams). It is not claimed to be the most powerful instantiation.
- **Direction is pinned BCVF-faithful (higher F predicts correct).** Wrong-direction outcomes count as failures; no sign-flip rescue.
- **N = 100 per benchmark** (matches §15.10/§13.10). AUC standard error at AUC ≈ 0.66 with N=100 is ~0.05–0.06; bands at 0.66 and 0.75 are hit/miss-able by sampling noise.
- **Single model size: Qwen2.5-7B-Instruct.** Does not speak to scaling at 13B / 32B / 70B.
- **Inherited from §15.10:** prompt-format vs §13.10 labeling regime (pinned `Q: {question}\nA:` regardless of how §13.10 generated labels); question-text source (dump field if present, else HF dataset by `q_idx`).
- **sklearn API surface (precautionary).** Module-level filter for the `penalty` FutureWarning is installed even though §15.11 uses only `roc_auc_score` (no LogisticRegression).

## Cross-phase comparison (disclosure only)

Phase 1 (§15.10) verdict-of-record: `PARTIAL_SIGNAL_IN_Z` (HaluEval-QA AUC=0.6686, ΔAUC=+0.008; TruthfulQA-MC AUC=0.6224, ΔAUC=−0.039 vs §13.10 entropy baseline 0.661).  
Phase 2 (§15.11) cascade outcome: `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` (HaluEval-QA AUC=0.461, ΔAUC=-0.200; TruthfulQA-MC AUC=0.485, ΔAUC=-0.176 vs the same baseline).  
This subsection is disclosure only and does not enter either phase's cascade decision. Both verdicts are independent §0.8-binding mechanical readouts; neither modifies the other.

## Audit-trail integrity

This result is a mechanical readout of the §15.11 cascade applied to the per-question phase-coherence scalar F over Qwen-7B's 29 per-layer last-token hidden states. Per §0.8 discipline, the cascade label is binding regardless of any post-hoc interpretation. §15.11 outputs do NOT modify any §13/§14/§15.x verdict-of-record (including §13.9's hold and §15.10's `PARTIAL_SIGNAL_IN_Z`); those are preserved. The interpretation firewall scanned this document for 26 Class-3 forbidden statements before write.
