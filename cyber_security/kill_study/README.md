# BCVF-Bio Adversarial Synthetic Kill Study

A deterministic, self-contained falsification study for one question:

> Does the BCVF **second-order** detector add measurable value beyond a tuned
> local-linear-trend (LLT) Kalman + CUSUM baseline once all non-detector
> protections are equalized?

**Scope:** synthetic only. No human data, no biometric-validity claim, no
production-security claim, no patent conclusion, no FSCS. See
`PREREGISTRATION.md` (written before results were interpreted) and
`results/RESULTS_RECORD.md` (the skeptical results record + limitations).

## Run

```bash
python -m cyber_security.kill_study.run          # full study (~2-3 min)
python -m cyber_security.kill_study.run --quick  # smoke run
python -m pytest cyber_security/kill_study/tests/ -q
```

Outputs land in `results/`: `manifest.json`, `events.jsonl` (raw per-event
records; archived compressed as `events.jsonl.gz`), `analysis.json`,
`RESULTS_RECORD.md`, and `plots/*.svg`.

## Design (why it can actually kill the hypothesis)

- **Fair, guards-equalized baseline.** Arms H (guarded BCVF composite) and I
  (guarded LLT+CUSUM composite) are structurally identical — verified-identity +
  disagreement + a temporal-change channel — differing *only* in that channel
  (BCVF second-order vs LLT-CUSUM innovation), each z-scored on the shared
  DEV-legit null. The strong baseline gets the same identity/disagreement
  information BCVF has; an identity-blind LLT baseline (arm E, kept as a pure
  reference) would rig the comparison toward BCVF.
- **Adversary-first.** The decisive families are slow/linear, smooth low-curvature,
  gate-aware poisoning, and a **detector-aware** trajectory constructed to evade
  the second-order signal specifically (worst case for BCVF).
- **Held-out.** Thresholds are tuned on DEV seeds and DEV parameter ranges;
  every reported number is EVAL (held-out seeds + held-out σ / separation /
  duration / missing-rate ranges).
- **Paired bootstrap** CIs over identical trajectory seeds; DET frontiers
  reported in full (no single-operating-point cherry-picking).
- **Mechanical verdict.** `analysis.py` emits the verdict from the preregistered
  decision rule; it is not editable after the fact. The results record also
  reports effect sizes and cross-axis coherence so a single trivial axis-win
  cannot be mistaken for a substantive result.

## Modules

| file | role |
|---|---|
| `config.py` | all knobs; dev/eval grids (disjoint); damage policy |
| `trajectories.py` | 12 deterministic trajectory families |
| `observers.py` | fast/slow observers, equalized guard layer, consumer |
| `detectors.py` | 9 arms (A–I) + composite channels |
| `calibration.py` | per-arm standardization on the DEV-legit null |
| `metrics.py` | per-event records + frontier reconstruction |
| `experiment.py` | orchestrator → manifest + raw records |
| `analysis.py` | aggregation, paired bootstrap, mechanical verdict |
| `plots.py` | SVG trajectories + DET frontier (no matplotlib) |
| `results_record.py` | skeptical results record generator |
| `run.py` | CLI entry point |
