# Natural-Language Phase Validation — Report (v1.6)

**Question A:** Does frozen Phase improve natural-language evidence use beyond a
sliding window? Measured by **B − A**.

> This report is populated from `results/aggregate.json`, `results/isolated_transfer.json`,
> `results/ablations.json`, and `results/resources.json`. Numbers are filled in
> after the committed run completes; sections are structured as
> **implemented / tested / demonstrated / unsupported / deferred**.

## Frozen baseline

See `EXPERIMENT_MANIFEST.json`. Git commit `6e29429…`, 98/98 tests pass,
FREEZE OK, CPU-only (4 cores, 15 GiB), torch 2.13.0.

## Arm definitions

- **A** local window only
- **B** local + frozen Phase
- **C** local + frozen Phase + bounded slots
- **C-no-Phase** local + bounded slots

Frozen `LightweightPhaseAttention` used unmodified (config in `EXPERIMENT_MANIFEST.json`).

## Implemented
- Natural-language enterprise task generator (7 families) with leakage-controlled
  splits (held-out entity names; shared, emittable answer vocabulary).
- Four arms composed from frozen modules; protected additive fusion.
- Shared LM + disclosed answer-position supervision; validation-based early stopping.
- No-quadratic audit, resource + ablation harnesses.

## (results filled post-run)
