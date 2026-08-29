# harmonic_event_collector_v2

Second and final preregistered attempt at the eventization E-GATE, testing two
targeted detector corrections on fresh data with the gate unchanged.

**Outcome: E-GATE FAILED on the fresh held-out set. Closed permanently** per
the owner-ratified terminal rule — no Stage B, no V3, no threshold changes, no
reasoning verdict. See `REPORT.md` for numbers and the process lesson;
`PREREGISTRATION.md` was frozen before implementation.

```
PREREGISTRATION.md   frozen protocol: two corrections, unchanged E-GATE, terminal rule
detectors_v2.py      V1 detector + protected/imputed references + envelope-ratio CUSUM
stage_a_v2.py        train-only fit -> freeze -> single held-out eval -> E-GATE
results/             frozen_thresholds.json, stage_a.json
REPORT.md            closure report
```

Reproduce: `python -m experiments.harmonic_event_collector_v2.stage_a_v2`
(the committed `results/stage_a.json` is the record of the single preregistered
held-out evaluation).

Contracts: V1 unmodified and its held-out data unused; stream generation and
the stat baseline imported unchanged from V1; nothing under
`symbolu/lightweight_phase/` imported or modified; the collector is not Phase;
no outcome reverses `experiments/phase_lc`.
