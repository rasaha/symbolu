# phase_temporal_collector

Isolated falsification experiment: do compact temporal summaries improve a
matched quadratic reader over ordinary statistical summaries, and if so, is the
learned Phase mechanism what earns the credit, or does fixed-clock harmonic
feature engineering suffice?

Read `PREREGISTRATION.md` first — gates G0–G2 and all failure conditions were
frozen in the commit that introduced it, before any training run. Results and
the verdict live in `REPORT.md` (written only after the sweep).

## Layout

```
PREREGISTRATION.md   frozen gates, arms, metric, failure conditions
signals.py           five synthetic stream families, held-out-frequency split
collectors.py        the six arms (A current, B stats, C harmonic, D real_rec,
                     E phase, F raw_quad)
reader.py            shared quadratic reader; <1% parameter matching via FFN width
harness.py           one (arm, seed) training/eval run -> results/<arm>_seed<n>.json
analyze.py           aggregates results, evaluates gates -> results/gates.json
results/             per-run JSON + gate evaluation
REPORT.md            post-run report and verdicts
```

## Reproduce

```
for seed in 0 1 2; do
  for arm in current stats harmonic real_rec phase raw_quad; do
    python -m experiments.phase_temporal_collector.harness --arm $arm --seed $seed
  done
done
python -m experiments.phase_temporal_collector.analyze
```

CPU-only (4 cores); the full sweep is ~1 hour. `--smoke` runs a 20-step wiring
check.

## Isolation contract

- Nothing under `symbolu/lightweight_phase/` is imported or modified. Arm E
  re-implements `reference_equations.md` §2–§5 conceptually at collector scale.
- No outcome here reverses the closed `experiments/phase_lc` verdict on Phase
  semantic retrieval, and nothing here is claimed beyond what the runs measure.
