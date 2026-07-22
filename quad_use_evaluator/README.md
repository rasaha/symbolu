# Universal Semantic Evaluator (USE) — CPU-only Falsification Study

A self-contained, CPU-only study asking whether a **read-only** Universal Semantic Evaluator —
the **U1–U5 peer-to-peer phase-coherence algorithm** run as a post-inference observer — can
predict the model's reasoning failures **better than standard confidence measures**, using only
the model's own internal computation. This is an attempt to **falsify** that claim; the null is
that internal coherence carries no predictive information beyond model confidence.

This is a **separate package**. It does not modify production code, Quad, the model architecture,
or the inference pipeline. It reuses the prior `quad_generative_regularization` (`qgr`) package
**read-only** (the authentic Quad model, deterministic MQAR, metrics). See `DESIGN.md` for the
design and `REPORT.md` for results and the verdict.

## Principle (read-only)

The model completes inference exactly as today. USE never changes attention, logits,
probabilities, retrieval, decoding, sampling, the KV path, the reasoning path, or generated
tokens. After the answer is produced, USE reads frozen internal states, extracts phase-like
channel states, and runs the U1–U5 coherence dynamics on a **detached** copy — computing a
*counterfactual* correction demand that is never applied to the model. No retrieval, no internet,
no second LLM. No inference-time control system is built (that is explicit future scope).

## USE core (U1–U5)

```
channels -> phase extraction -> U1 pairwise phase coherence -> U2 global coherence
   -> U3 peer gradient -> U4 counterfactual correction demand -> U5 convergence diagnostics
S_USE = { C_windowed, R_initial, R_final, ΔR, E_correction, D_max, D_mean, T_conv, R_unresolved }
```

## Layout

```
DESIGN.md               experimental design (READ FIRST)
REPORT.md               results, baselines, calibration, ablation, verdict, recommendation
use/
  _qgr_path.py          read-only bootstrap of the prior qgr package
  capture.py            read-only forward-hook capture of frozen internal states
  channels.py           channel sets (head/layer/quad/value/residual/full); read-only per-head recompute
  phases.py             three preregistered non-learned phase mappings
  kuramoto.py           U1-U5 dynamics (pairwise/global coherence, gradient, relaxation, convergence)
  use_signals.py        assemble S_USE per query
  baselines.py          confidence baselines (token prob, logprob, entropy, margin, seq conf, attn entropy, random)
  metrics.py            AUROC / AUPRC / F1 / Brier / ECE / reliability
  predict.py            univariate power + OOF logistic combos (no leakage)
  stats.py              DeLong test + bootstrap AUROC CIs
  experiment.py         orchestration, USE-vs-baseline tests, verdict
  ablation.py           channel-set / mapping / per-signal ablations
  failure_analysis.py   USE-vs-confidence agreement/disagreement categories
  plots.py              figures
tests/                  read-only capture, U1-U5 correctness, no-leakage OOF, determinism
run_use.py              main driver -> RESULTS/
```

## Reproduce

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q               # 12 tests (incl. read-only capture)
OMP_NUM_THREADS=4 python run_use.py --threads 4 --seeds 0 1 2 --n-batches 40   # -> RESULTS/
# quick smoke: python run_use.py --quick
```

Deterministic given seeds. Outputs land in `RESULTS/` (`use_results.json`, `plots/`).
