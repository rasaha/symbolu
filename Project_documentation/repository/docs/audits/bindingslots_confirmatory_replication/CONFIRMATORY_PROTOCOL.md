# Confirmatory protocol

Machine-readable: [`CONFIRMATORY_PROTOCOL.json`](./CONFIRMATORY_PROTOCOL.json) (canonical copy of
`experiments/bindingslots_confirmatory/preregistration.json`). Full narrative:
[`experiments/bindingslots_confirmatory/preregistration.md`](../../../experiments/bindingslots_confirmatory/preregistration.md).

## Execution order (frozen)

1. live-state audit → 2. recover frozen CR1 → 3. select fresh seeds 13–17 → 4. write full
preregistration → 5. torch-free integrity verification → 6. commit preregistration → 7. **push
preregistration** → 8. record preregistration commit → 9. run B0 and CR1 (and A+ control) → 10.
interruption-safe state → 11. complete all five seeds → 12. frozen classifier → 13. causal gates →
14. quality and distance gates → 15. curated artifacts → 16. tests + verifiers → 17. final report →
18. commit results → 19. push branch → 20. open one PR → 21. leave unmerged → 22. stop.

**No training begins before the preregistration commit is pushed.**

## Arms

`A+` (window-only control), `B0` (unscaffolded baseline), `CR1` (intervention). All three are in the
frozen Stage B matrix; A+ is the reference for the frozen formation/margin/causal/quality gates.

## Primary criterion

`REPLICATED_SLOT_FORMATION_STABILIZATION` iff C1..C11 all pass (≥4/5 form, >B0, ≥4/5 wins, mean
≥0.080, median ≥0.050, quality, distance, slots-off collapse every forming seed, randomized-address
collapse every forming seed, integrity, no deviation). See
[`CLASSIFIER_SPEC.md`](./CLASSIFIER_SPEC.md) and [`CAUSAL_GATE_SPEC.md`](./CAUSAL_GATE_SPEC.md).

## Discipline

3/5 ≠ nearly replicated; one causally-unclean forming seed fails the replication; causal results
never averaged; no best-checkpoint selection; no outcome-based seed replacement; no threshold
changes; `PROVISIONALLY_STABILIZED` is not a valid confirmatory verdict.
