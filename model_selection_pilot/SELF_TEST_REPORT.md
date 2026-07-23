# Self-Test Report — Harness Validation (NOT Real-Model Evidence)

> **READ THIS FIRST.** Every number in this report comes from a **deterministic
> offline STUB**, because no real model could be executed (see `PILOT_STATUS.md`).
> These numbers exist to prove the harness *runs correctly and computes every
> mandated metric and ablation*. They are **not evidence about real routing value**,
> and they do **not** satisfy or falsify the pre-registered hypothesis. A critical
> circularity applies: the stub's telemetry is derived from the same stub that
> generates outcomes, so the policy's mature-regime advantage is partly tautological.
> The empirical question stays OPEN until real models run.

---

## What the self-test confirms about the harness

- Full counterfactual runs (every eligible model on every task), schema validation,
  deterministic scoring, cost accounting, and decision records all execute end to end.
- All seven arms (A, B, C, D, E, F1, F2, G) route across 28 shadow tasks / 3 regimes.
- Both mandated ablations compute: **F1 vs F2** (quality-gate) and **F2 vs G**
  (cold-start self-assessment).
- Cost guard produces a dry-run (~$1.36 combined worst-case) and enforces a hard cap.
- Explanation completeness is **100%** for F2 and G; routing is deterministic;
  stability under ±1% telemetry perturbation is **100%** (F2, mature).
- 17/17 behavior tests pass (information boundary, hard-policy, min-quality gate, cost
  guard, provenance, telemetry versioning, fallback ordering, self-assessment field
  restrictions, decision-record consistency, zero-eligible).

## Stub numbers (illustrative mechanics only — not evidence)

Mean selection regret (lower = better), shadow set:

| Arm | regret | violations | qok (abstain=fail) | expensive-avoided |
|---|---:|---:|---:|---:|
| A fixed default | 0.406 | 0.107 | 0.679 | 0.50 |
| B strongest-eligible | 0.402 | 0.000 | 0.643 | 0.107 |
| C cheapest-eligible | 0.341 | 0.000 | 0.286 | 0.286 |
| D static rules | 0.313 | 0.000 | 0.679 | 0.321 |
| E benchmark-only | 0.334 | 0.000 | 0.714 | 0.000 |
| F1 policy (soft quality), mature | 0.159 | 0.000 | 0.500 | 0.393 |
| **F2 policy (quality gate), mature** | **0.083** | 0.000 | 0.500 | 0.464 |
| G policy + self-assessment, mature | 0.129 | 0.000 | 0.464 | 0.393 |

Mandated ablations (stub):

- **F1 → F2 (quality-gate correction):** mature regret **0.159 → 0.083 (−48%)**;
  abstention +0.14 (the gate defers tasks where it predicts no model meets the bar).
  This is the mechanic the correction was designed to add, and the harness measures it.
- **F2 → G (cold-start self-assessment):** cold-start regret barely moves (**−0.010**)
  while cost-per-success rises ~**8×** (the preflight tax); in partial/mature G is
  *worse* than F2 (regret +0.06 / +0.05). In this stub, task-shape-only advisory is a
  weak, overconfident signal that mostly adds noise + cost. Whether that holds for real
  models is exactly what the pre-registered ablation must decide.

## What the self-test cannot tell us

- Whether real benchmarks/telemetry predict real model quality (the circularity above).
- Advertised-vs-effective context, real schema-support failures, version drift, provider
  errors, rate limits — the failure modes the pilot is designed to catch **require real
  endpoints** and did not occur in the stub.
- Any commercial figure (cost reduction, quality failures introduced): the stub's
  economics are modeled from registry prices, not billed.

**Bottom line:** the machine is built and correct; the experiment has not been run.
