# harmonic_real_data

Preregistered real-data test of continuous fixed-harmonic summary tokens on
the official Microsoft Azure Functions 2019 trace: do they improve a quadratic
reader's demand forecasts over statistical summaries, persistence, and daily
seasonal-naive — using the two-memory design (summary tokens + retrievable
minute-level raw evidence, no inferred event bottleneck)?

Read in order: `PROVENANCE.md` (authoritative source, digests, license),
`PREREGISTRATION.md` (frozen gates and protocol), `REPORT.md` (outcome).

## Layout

```
PROVENANCE.md          source URL, release tag, sizes, SHA-256 digests, CC-BY
DATA_DIGESTS.txt       per-file SHA-256 of the 14 invocation CSVs
DATA_SIZES.txt         per-file byte sizes
PREREGISTRATION.md     frozen split, cohort rule, arms, gates V/H/S
frozen_functions.json  the 200-function cohort (train-days-only selection)
select_functions.py    eligibility + cohort freeze (d01-d08 only)
build_series.py        cohort minute matrix -> scratchpad npz (never committed)
features.py            deterministic tracks: stats/harmonic/retrieval/targets
data_assembly.py       track cache + per-query token gather
arms.py                parameter-matched quadratic readers (S/HS/SR/HR)
train.py               train on d01-d08, select on d09-d10 (dev envelope)
evaluate_heldout.py    ONE-SHOT d11-d14 evaluation + gates
results/               dev_metrics.json, heldout.json
```

## Reproduce

1. Download the archive per `PROVENANCE.md`, verify SHA-256, extract the 14
   invocation CSVs (dataset stays outside Git).
2. `python -m experiments.harmonic_real_data.select_functions <data_dir>`
3. `python -m experiments.harmonic_real_data.build_series <data_dir> <npz>`
4. `python -m experiments.harmonic_real_data.train <npz> <model_dir>`
5. `python -m experiments.harmonic_real_data.evaluate_heldout <npz> <model_dir>`

## Contracts

Nothing under `symbolu/lightweight_phase/` imported or modified; the collector
is not Phase; no inferred event bottleneck; intraday+daily harmonic claims
only (14-day trace — no weekly claims); all non-claim contracts of
`experiments/phase_temporal_collector` and the closed
`harmonic_event_collector` experiments carry forward.
