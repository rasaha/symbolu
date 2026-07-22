# SCC Observer — CPU-only Falsification Study

Does a proposed **Semantic Coherence Controller (SCC)** contain *independent* predictive
information about model correctness, **beyond confidence, entailment, and evidence-grounding**?
SCC is tested as **four separate, falsifiable hypotheses** — S (semantic similarity), R (relational
preservation), E (evidence support), T (inference stability) — each of which must independently
justify its existence. This is a falsification study, not a proof of SCC.

Separate package; reuses the prior `qgr`, `quad_use_evaluator` (`use`), and
`quad_perturbation_consistency` (`qpc`) packages **read-only**. Nothing in Quad, the MQAR
benchmark, the model, or any previous package is modified. All analysis is post-inference and
observer-only — no retraining, no regularization, no inference-time control system.

See `DESIGN.md` for the design and `REPORT.md` for results and the verdict.

## Layout

```
DESIGN.md / REPORT.md / README.md
scc/
  _paths.py        read-only bootstrap of prior packages
  claims.py        decode per-query claim (k_q -> v_pred) + context + retrieved key
  features_S.py    semantic similarity (representation cosine as a feature)
  features_R.py    relational preservation (structural)
  features_E.py    evidence support (closed-world symbolic; open-world documented, not implemented)
  features_T.py    inference stability under semantic-equivalence perturbations (reuses qpc)
  baselines.py     A confidence (reuses use), B entailment proxy, C grounding
  dataset.py       per-query feature matrix + label across seeds/conditions
  arms.py          feature-group and arm definitions
  evaluate.py      OOF logistic, DeLong incremental tests, calibration, verdict enum
  redundancy.py    overlap of each SCC term with baselines
  plots.py         figures
tests/             read-only, feature sanity (evidence=oracle), no-leakage OOF
run_scc.py         main driver -> RESULTS/
```

## Reproduce

```bash
pip install -r requirements.txt
OMP_NUM_THREADS=4 python -m pytest tests/ -q
OMP_NUM_THREADS=4 python run_scc.py --threads 4 --seeds 0 1 2 --n-batches 30 --M 4   # -> RESULTS/
# quick smoke: python run_scc.py --quick
```

Deterministic given seeds. Outputs in `RESULTS/` (`scc_results.json`, `plots/`).
