# §15.10 Phase 1 — Supervised linear truth-probe (result)

_Schema version: `15.10`._  
_Model: `Qwen/Qwen2.5-7B-Instruct`; layer index: `-1`; hidden dim: `3584`; prompt format: `Q: {question}\nA:`._

## Cascade verdict (mechanical readout)

**Label:** `PARTIAL_SIGNAL_IN_Z`

**Rationale:** PARTIAL: not STRONG; AUC ≥ 0.66 on at least one benchmark (HaluEval=0.669, TruthfulQA-MC=0.622) AND ΔAUC > 0 on at least one benchmark (ΔHaluEval=+0.008, ΔTruthfulQA-MC=-0.039).

| benchmark | probe AUC (OOF) | §13.10 baseline AUC | ΔAUC |
|---|---|---|---|
| HaluEval-QA | 0.669 | 0.661 | +0.008 |
| TruthfulQA-MC | 0.622 | 0.661 | -0.039 |

## Probe details — HaluEval-QA

- N questions: 100 (correct: 30, wrong: 70)
- π observed: 0.300 (pinned: 0.300)
- Probe OOF AUC: **0.669** (§13.10 baseline: 0.661; ΔAUC: +0.008)
- Per-fold AUCs: [0.643, 0.762, 0.607, 0.5, 0.75]
- CV std (AUC): 0.108
- OOF accuracy @ p≥0.5: 0.680
- OOF Brier: 0.2461

**Selective-prediction operating points:**

| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |
|---|----|-----|----------|------------|------------|----------|
| 0.40 | 0.0249 | 0.550 | 0.550 | 0.400 | 55 | yes |
| 0.50 | 0.1860 | 0.280 | 0.280 | 0.500 | 28 | yes |
| 0.75 | — | 0.000 | 0.000 | — | 0 | no |

## Probe details — TruthfulQA-MC

- N questions: 100 (correct: 25, wrong: 75)
- π observed: 0.250 (pinned: 0.250)
- Probe OOF AUC: **0.622** (§13.10 baseline: 0.661; ΔAUC: -0.039)
- Per-fold AUCs: [0.707, 0.373, 0.68, 0.747, 0.533]
- CV std (AUC): 0.154
- OOF accuracy @ p≥0.5: 0.740
- OOF Brier: 0.2161

**Selective-prediction operating points:**

| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |
|---|----|-----|----------|------------|------------|----------|
| 0.35 | 0.0420 | 0.400 | 0.400 | 0.350 | 40 | yes |
| 0.50 | — | 0.000 | 0.000 | — | 0 | no |
| 0.75 | — | 0.000 | 0.000 | — | 0 | no |

## Pinned configuration (§15.10 §0.8-binding)

- Probe: L2 LogisticRegression, C=1.0, solver=lbfgs, max_iter=1000
- CV: 5-fold stratified, shuffle=True, random_state=15
- Per-fold StandardScaler fit on train, applied to val
- Selective-prediction floor: N_MIN=10
- Cascade thresholds: STRONG AUC≥0.75 AND ΔAUC≥+0.05 (both benchmarks); PARTIAL AUC≥0.66 AND ΔAUC>0 (at least one); otherwise NO_MATERIAL

## Caveats (§0.8-disclosed)

- **Prompt format vs §13.10 labeling regime.** §15.10 pinned `Q: {question}\nA:` regardless of how §13.10 generated the correctness labels. §13.10's HaluEval producer defaults to no-context (matches the pinned format), but `--include-context` would prepend the HaluEval `knowledge` passage. Without an explicit pin to the §13.10 invocation, we cannot rule out a prompt-template mismatch on HaluEval. This is the standard linear truth-probe convention; the cascade verdict is binding regardless.
- **Question text source.** Question text used for the Qwen-7B forward pass is read from the §13.10 dump's `question` field when present on every record, else loaded from the HuggingFace dataset by `q_idx` alignment.
- **sklearn API surface.** The probe call passes `penalty='l2'` explicitly; sklearn 1.8 deprecated this kwarg (still accepted), and sklearn 1.10 will remove it. A targeted FutureWarning filter is installed at module load; if the runpod's sklearn ≥ 1.10, the script will exit 7 (PROBE_FAILED) with a clear TypeError, unambiguously diagnosable.

## Audit-trail integrity

This result is a mechanical readout of the §15.10 cascade applied to OOF probe outputs. Per §0.8 discipline, the cascade label is binding regardless of any post-hoc interpretation, and §15.10 outputs do NOT modify any §13/§14/§15.x verdict-of-record. The interpretation firewall scanned this document for Class-3 forbidden statements before write.
