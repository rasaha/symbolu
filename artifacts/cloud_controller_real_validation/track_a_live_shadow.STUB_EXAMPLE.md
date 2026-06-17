> ⚠️ **THIS IS A WIRING-SHAPE EXAMPLE, NOT A CLUSTER RUN.** It was produced by
> `tests/cloud_controller/test_shadow_integration.py`'s HTTP **stub** Prometheus in
> the build environment (no Docker/k8s available). It demonstrates the *shape* of
> the report and proves the wiring runs over real HTTP. The numbers are from a
> synthetic stub, **not** `live-shadow-self-run`. Real numbers come from
> `deploy/local-shadow/` on a Docker host.

---

# Live-shadow proof-of-value — STUB wiring demo (NOT a cluster)

> **Label: `live-shadow-self-run`.** Real cluster, real Prometheus, real HPA, OUR injected faults. The controller ran **read-only** alongside HPA — zero write permissions, zero actuation. Savings shown are what the guard *would* have saved; they are NOT independently verified (that is the third-party rung, still pending).

- Cycles observed: **60**

## Decision quality vs HPA
- Decisions: 60 (24 agreements, 36 divergences)
- Controller correct: 0 · HPA correct: 0
- Estimated cost saved: **$0.00** (@ $0.03/replica·min)

## Futility guard (counterfactual — never actuated)
- Scale-outs observed: 0
- **Futile scale-outs the guard would have blocked: 0**
- Activation reason: `n/a`

## SLO
- **SLO regressions caused by the guard: 0** (0 by construction — read-only)
- Observed SLO-breach cycles in the environment: 0 (context; driven by the injected faults)

## Notes
- Controller ran read-only in shadow; the guard's blocks are a counterfactual, never applied to the cluster.
- Cost/divergence verdicts are correlation, not causation (see DivergenceTracker docstring).