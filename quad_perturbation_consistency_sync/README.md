# Quad Perturbation-Consistency Study

A **separate research track** testing whether *same-head perturbation consistency* improves Quad
retrieval generalization **without supervising query→key labels**. It imports the frozen
`quad_generative_regularization` package (`qgr`) as a **read-only library** — the existing Quad
track and its conclusions are unmodified.

This is a **falsification** study. The bar is **BD-A (task-only)**, not BD-D. The null
hypothesis — task-only learning already finds the best retrieval organization — is rejected only
if BD-Sync **strictly and significantly** exceeds BD-A while passing both guardrails.

No USE, phase, synchronization across heads/layers, routing, gating, entropy/temperature
penalties, teacher forcing, or inference-time component. The only new element is a training-only
JS-consistency term.

## Idea

For each base sample `x`, a semantic-equivalent perturbation `x̃` preserves every query→value
relation but changes irrelevant structure (pair order, position, distractor count). Per head, the
retrieval distribution over canonical **pair buckets** is required to be consistent:
`L_sync = mean_h JS(A_h(x), stopgrad(A_h(x̃)))`. No key is labelled; the task loss alone decides
which pair is correct.

## Layout

```
PROTOCOL.md              pre-registered protocol (arms, metrics, guardrails, decision rule)
SYNC_REPORT.md           final report + decision category + recommendation
qpc/
  paired_mqar.py         paired (x, x̃) generation + canonical pair-bucket mapping + stages
  consistency.py         pair-bucket distributions + symmetric JS consistency loss
  train_sync.py          unified 5-arm training loop (imports qgr)
  diagnostics.py         entropy / cross-head diversity / specialization / drift
  sync_plots.py          plots
tests/test_qpc.py        8 tests (answer-preserving, label-free, guardrail plumbing, determinism)
run_sync.py              driver -> RESULTS_SYNC/
RESULTS_SYNC/            sync_results.json, sync_results.csv, plots/, pilot.log
```

## Arms

`BD-A` (task-only bar) · `BD-D` (labelled Quad aux) · `BD-Sync` (JS consistency) ·
`BD-Sync-Early` (consistency first 25% only) · `Shuffled-Pair` (unrelated-partner control).

## Reproduce

```bash
pip install -r ../quad_generative_regularization/requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q            # 8 tests
OMP_NUM_THREADS=4 python run_sync.py --threads 4        # 5 arms x 5 seeds -> RESULTS_SYNC/
OMP_NUM_THREADS=4 python run_sync.py --quick            # fast integration smoke
```

Frozen: bounded α=4, λ_sync=0.5, 2500 steps, seeds {0..4}. See `PROTOCOL.md` and `SYNC_REPORT.md`.
