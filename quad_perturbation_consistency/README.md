# Quad Perturbation-Consistency — CPU-only Falsification Study

A self-contained, CPU-only study asking whether a **same-head perturbation-consistency
objective, using no retrieval labels**, can improve Quad-retrieval generalization **beyond the
task-only bounded baseline (BD-A)**. This is an attempt to **falsify** that hypothesis; the null
is that task-only learning already finds the best retrieval organization.

This is a **separate package**. It does not modify any production code or any previous research
package — it reuses the prior `quad_generative_regularization` (`qgr`) package **read-only** (the
authentic Quad model, deterministic MQAR, task loss, metrics, and the read-only causal-ablation
tools). See `DESIGN.md` for the full design and `REPORT.md` for results and the verdict.

## What is (and is not) implemented

Implemented: a **training-time** consistency objective — same-head only, symmetric
Jensen-Shannon divergence, stop-gradient (or EMA) self-target, small fixed coefficient, read
from the model's own forward-path Quad score. **No** retrieval labels, cross-head/-layer
synchronization, entropy penalties, temperature/normalization/architecture/inference changes,
USE/phase, routing, or teacher forcing. A λ=0 run is **bit-identical** to BD-A.

## Arms

| Arm | Definition |
|-----|-----------|
| **BD-A** | bounded, task-only — **the benchmark** |
| **BD-D** | bounded + Quad auxiliary (retrieval labels) — existing baseline |
| **BD-Sync** | BD-A + λ·same-head JS consistency (full duration) — proposed |
| **BD-Sync-Early** | consistency only for the first 10% of steps |
| **BD-Shuffled** | same machinery, key alignment randomly permuted — generic-regularization control |

## Layout

```
DESIGN.md                experimental design (READ FIRST)
PILOT_RECORD.md          disjoint-seed pilot; the single frozen lambda
REPORT.md                results, guardrails, statistics, verdict, recommendation
qpc/
  _qgr_path.py           read-only bootstrap of the prior qgr package
  perturbations.py       semantic-equivalence views + canonical token-identity alignment
  consistency.py         same-head symmetric-JS objective, stop-grad/EMA, shuffled control
  train_sync.py          task-only + consistency add-on loop (λ=0 == BD-A, bit-identical)
  health.py              entropy / diversity / specialization / stability + Guardrail-2
  progressive.py         progressive perturbation degradation curves
  stats.py               paired significance vs BD-A (Wilcoxon, bootstrap, t)
  experiment.py          orchestration, guardrails, aggregation, verdict
  plots.py               all figures
tests/                   correctness + λ=0 equivalence tests
run_pilot.py             freeze lambda on disjoint seeds  -> RESULTS/pilot.json
run_consistency.py       confirmatory 5-arm x N-seed run  -> RESULTS/
```

## Reproduce

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q          # correctness + equivalence
OMP_NUM_THREADS=4 python run_pilot.py --threads 4     # freeze lambda (disjoint seeds)
OMP_NUM_THREADS=4 python run_consistency.py --threads 4   # confirmatory run -> RESULTS/
# quick smoke: python run_consistency.py --quick --lambda 0.1
```

Everything is deterministic given the frozen config and seeds. Outputs land in `RESULTS/`
(`consistency_results.json`, `.csv`, `plots/`).
