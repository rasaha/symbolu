# Quad Generative Regularization — CPU-only Falsification Study

A self-contained, CPU-only proof-of-concept evaluating whether a **training-only auxiliary
loss applied to the authentic Quad generative score** improves associative binding
(MQAR) beyond generic relational supervision — while leaving the deployed inference
architecture unchanged.

This package implements the study described in the v1.3 implementation spec. It does **not**
implement or test any phase / synchronization / Kuramoto / USE mechanism. It evaluates
**Quad-native training regularization only** (see `QUAD_TRACEABILITY.md`).

## What "Quad" means here

The authoritative Quad generative scorer is `BindingCacheQuadQuery`
(`symbolu/phase_transformer.py:3507`, canonical per
`docs/PHASE_QUAD_LOCAL_ATTENTION_ALGORITHM.md` §4). Its score is a per-head, causally-masked,
candidate-comparable scaled dot product

```
S^Q_{i,j} = ( W_q · LN_q(x_i) ) · ( W_k · LN_m(m_j) ) / sqrt(d_h)     (causal: j ≤ i)
```

which Quad uses generatively (Top-K / softmax over candidate keys). It is mathematically
**separable from phase** (phase only supplies the memory tensor `m`); this study uses the
separable phase-free core `m := hidden states`. Full trace, shapes, and the compatibility
gate are in `QUAD_TRACEABILITY.md`.

## Experimental arms

| Arm | Loss | Role |
|-----|------|------|
| **A** | `L_task` | baseline |
| **C** | `L_task + λ·L_generic` | generic relational control — same candidate supervision on an equal-capacity **off-path** learned relation head (not the Quad score) |
| **D** | `L_task + λ·L_QuadAux` | proposed — same supervision on the model's **own forward-path Quad score** |
| **D0** | Arm-D code path, λ=0 | deterministic equivalence test vs A (must be bit-identical) |

The auxiliary objective is **Option B — native Quad candidate classification**: softmax of
`S^Q_{i,·}` over the causally-visible candidate keys, NLL of the correct earlier key
(query → correct earlier key; spec §7, §8). Everything Arm C and D see (query positions,
positive labels, candidate/negative sets, causal restriction, temperature) is identical; the
only difference is which score field the loss reads.

## Layout

```
QUAD_TRACEABILITY.md   Phase-0 authoritative trace + compatibility gate (READ FIRST)
PILOT_RECORD.md        bounded-pilot record and frozen hyperparameters
REPORT.md              final technical report, classifications, verdict
configs/frozen.json    the single frozen, pre-registered protocol
qgr/
  quad_model.py        Quad-scoring CPU transformer (exposes S^Q) + GenericRelationHead
  mqar.py              deterministic MQAR generation, splits, candidate/label metadata
  losses.py            task loss, Quad aux (Option B/C), generic relational, diagnostics
  train.py             training loop; arms A/C/D/D0; gradient diagnostics; shuffled-label control
  metrics.py           MQAR exact-match accuracy; Quad mechanism metrics
  experiment.py        orchestration, positive-signal gate, classification, verdict
  plotting.py          all required plots
tests/                 21 tests covering spec §22 items 1-19
run_screen.py          main driver -> RESULTS/
RESULTS/               results.json, results.csv, plots/, screen_run.log
```

## Reproduce

```bash
# 1. environment (CPU-only). On a restricted proxy, torch installs from PyPI (runs on CPU).
pip install -r requirements.txt

# 2. all tests must pass before the main run (spec §22)
OMP_NUM_THREADS=4 python -m pytest tests/ -q

# 3. full 3-seed screen (Phase 0B validations + Phase 2 screen + plots + verdict)
OMP_NUM_THREADS=4 python run_screen.py --threads 4

# quick smoke (2 seeds, short) for iteration:
OMP_NUM_THREADS=4 python run_screen.py --quick
```

Outputs land in `RESULTS/`: `results.json` (full machine-readable record), `results.csv`
(per-arm/per-seed table), and `plots/` (8 figures). Everything is deterministic given the
frozen config and seeds.

## Determinism & inference invariance

- Same seed → bit-identical model init, data order, and final parameters (`tests/test_equivalence.py`).
- Arm A and Arm D0 (λ=0) produce **bit-identical** parameters — exposing the Quad score for the
  aux loss changes nothing in the forward/optimization path.
- Inference output is **identical** with the auxiliary-only objects disabled/deleted; the
  Arm-C relation head is training-only and never part of the deployed model.

See `REPORT.md` for results and the verdict.
