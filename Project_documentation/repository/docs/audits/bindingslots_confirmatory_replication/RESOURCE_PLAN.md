# Resource plan

## Compute

- 3 arms × 5 seeds = 15 training runs at the frozen 1200-step budget, CPU, fp32, threads=4.
- Measured wall time: `A+` (window-only) ≈ 200 s/seed; `B0` ≈ 800 s/seed; `CR1` ≈ 950 s/seed
  (includes step-1200 eval + causal ablations). Total ≈ 2.5–3 h.
- torch is **not** preinstalled here and `download.pytorch.org` is egress-blocked; torch 2.2.2 is
  installed from PyPI (allowed host) for the run.

## Idempotence / resumability

`run_confirmatory.py` writes one JSON per `(arm, seed)` and skips completed ones on restart, so the
run survives container recycling. Each completion updates `results/manifest.json:seed_arm_status`.
Restart/interruption events are appended to `results/manifest.json:restart_events`.

## Resource-blocked handling

If torch cannot be installed or a run cannot complete for all 3 arms × 5 seeds, the classifier emits
`CONFIRMATORY_RESOURCE_BLOCKED` (an INVALID verdict) rather than any scientific verdict. **No result
is ever fabricated.** The preregistration, harness, classifier, gates, tests, and CI are complete
and committed regardless, so the run is reproducible on any torch-capable host via the documented
one-command entry point.

## Storage

Curated per-seed + aggregate artifacts are committed. Large transient checkpoints are not committed
(repository policy). Raw-trace checksums are retained.
