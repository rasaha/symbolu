# harmonic_event_collector

Isolated, preregistered falsification experiment: can a fixed-clock harmonic
collector turn long raw streams into a small, trustworthy set of temporal
events (Stage A), and do harmonic summaries then improve event-based quadratic
reasoning (Stage B)?

**Outcome: closed at Stage A — E-GATE FAILED on the held-out set (eventization
NOT SUPPORTED at tested scale). Stage B was never run and no reasoning verdict
exists.** See `REPORT.md` for the numbers and `PREREGISTRATION.md` (frozen
before implementation) for the gates.

## Layout

```
PREREGISTRATION.md   frozen gates (E/V/H), stream families, protocol
streams.py           event-labelled synthetic streams (Stage A: T=4096; Stage B: T=768)
detectors.py         StatChangeDetector baseline + HarmonicEventCollector
stage_a.py           train-only threshold fit -> freeze -> single held-out eval -> E-GATE
results/             frozen_thresholds.json, stage_a.json
REPORT.md            outcome and audit trail
```

Stage B modules were intentionally never written: the preregistered failure
condition stops the experiment at a failed E-GATE.

## Reproduce

```
python -m experiments.harmonic_event_collector.stage_a
```

Note: reproducing re-runs the full fit+eval pipeline; the committed
`results/stage_a.json` is the record of the single preregistered held-out
evaluation.

## Contracts

- Nothing under `symbolu/lightweight_phase/` is imported or modified.
- The collector is a classical mechanism (clock bank + seasonal expectation +
  change channels) and is never called Phase.
- No outcome here reverses `experiments/phase_lc`, and the Sweep 3 G1 result
  of `experiments/phase_temporal_collector` stands unaffected.
- Further eventization work is a new experiment requiring new owner
  ratification, with a fresh held-out set.
