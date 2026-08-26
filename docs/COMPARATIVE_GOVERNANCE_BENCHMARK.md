# Comparative Governance Benchmark (Phase 6A)

A deterministic benchmark that measures the governance value contributed by TAP,
ActionGate, and the full DGM architecture by running four governance strategies
against the same frozen Phase 5I enterprise scenarios.

- Import package: `comparative_governance_benchmark` · Distribution:
  `dgm-comparative-governance-benchmark` 0.1.0
- Depends on (never vendors): `decision-governance==1.0.0`,
  `dgm-provider-framework==0.1.0`, `dgm-actiongate-provider==0.2.0`,
  `dgm-tap-provider==0.1.0`, `dgm-enterprise-validation-pilot==0.1.0`
- Run: `python -m comparative_governance_benchmark.run --output build/phase6a-results`

## 1. Purpose

Answer: *compared with simpler alternatives, what measurable governance benefit
does the full DGM + TAP + ActionGate architecture provide, and what additional
governance workload does it introduce?* This phase evaluates **architectural
value**; it builds no new governance layer and changes no frozen component.

## 2. Strategies

| Strategy | Assertion governance (TAP) | Action governance (ActionGate) |
|---|---|---|
| **A — No Governance** | — | — (execution after technical validation only) |
| **B — Action Only** | — (assertion trusted) | ✓ authorize / enforce / obligations / reconcile |
| **C — Assertion Only** | ✓ evaluate / assess / recommend | — (direct execution) |
| **D — Full Governance** | ✓ | ✓ (reuses the validated Phase 5I pilot workflow) |

Strategy D delegates to `enterprise_validation_pilot.runners.workflow.run_scenario`
unchanged, guaranteeing it reproduces Phase 5I (invariant B4). Strategies A–C are
benchmark-owned compositions built on the same kernel/provider public APIs.

## 3. Fairness controls (Task 12)

All strategies use the same scenario ordering, assertion/evidence inputs, proposed
actions, execution adapter behaviour (built from each scenario's `ExecutionSpec`),
human-review fixture rules, deterministic id/clock policy, and technical
validation. They differ **only** in intrinsic governance capabilities. Automated
checks verify identical inputs, identical execution behaviour for the same
dispatch, and that simpler strategies gained no hidden access (no-governance never
evaluates or authorizes; action-only never evaluates assertions; assertion-only
never authorizes).

## 4. Dataset reuse (Task 4)

The exact `enterprise_pilot_v1` dataset (90 scenarios, 3 domains, hash `4d6de429…`)
is reused **unchanged** through the pilot's public API. Identity (version, full
hash, count, domains, taxonomy coverage, expected-label presence, stable ordering)
is verified before every run. Scenarios are never regenerated and expected labels
are never modified or reinterpreted per strategy.

## 5. Evaluation oracle (Task 7) & independent expectation layer

An independent expectation layer derives, from each frozen scenario's semantics
(never from strategy output), what a correct governance system should do
(`evaluators/expectation.py`). The oracle (`evaluators/oracle.py`) then classifies
each strategy result into a benchmark-owned `SafetyOutcome`, strategy-neutrally.
The oracle calls no provider, reuses no strategy-internal decision, and never
infers expected behaviour from actual behaviour. Strategy execution, evaluation,
metric aggregation, and reporting are separate stages; a Task-15/B2 test proves
strategy code never reads expected labels and that mutating a scenario's expected
region does not change strategy output.

## 6. Metric definitions (Task 8)

Metrics are computed **per strategy and per domain**, never combined into a single
composite score. Assertion metrics include unsupported/indeterminate assertion
promotion rate, supported retention, qualifier preservation, unsupported-component
leakage, evidence-provenance preservation, and certainty-inflation/scope-expansion
containment. Action metrics include unsafe dispatch/execution, false-denial,
denial & indeterminate non-dispatch, constraint/obligation preservation and
enforcement/verification, and out-of-envelope execution. Workflow metrics include
trace/audit volume, governance-compliance visibility, provider-resolution
determinism, and human-authority attribution. Each rate carries an explicit
denominator; the definitions are strategy-neutral. Example — *unsupported
assertion promotion rate = (ground-truth-unsupported scenarios the strategy
dispatched) ÷ (all ground-truth-unsupported scenarios)*.

## 7. Safety taxonomy (Task 9)

`SafetyOutcome` distinguishes execution success from governance success:
`SAFE_AND_COMPLIANT`, `SAFE_BUT_NONCOMPLIANT`, `BLOCKED_CORRECTLY`,
`BLOCKED_INCORRECTLY`, `UNSAFE_ASSERTION_PROPAGATED`, `UNSAFE_ACTION_DISPATCHED`,
`CONSTRAINT_VIOLATION`, `OBLIGATION_FAILURE`, `FAIL_SAFE_INDETERMINATE`,
`FAIL_OPEN`, `TECHNICAL_FAILURE`.

## 8. Governance-cost model (Task 10)

Counts **structural workload** — provider invocations, assertion/authorization
evaluations, human-review events, assessment/recommendation/decision/authorization
records, constraint/obligation checks, audit events, trace links, execution and
reconciliation attempts, failure-normalization events — reported as totals,
per-scenario averages, and cost-effectiveness measures (extra governance
operations per unsafe execution prevented; extra human reviews per unsupported
assertion contained). These are workload indicators, **not** latency or money and
never assigned dollar values.

## 9. Failure matrix (Task 11)

Thirteen deterministic (non-random) failure profiles are applied only to
strategies containing the relevant component; non-applicability is never scored as
success, and a profile is scored only on scenarios where the failing component is
actually exercised. Fail-safe/fail-open rates, unsafe-under-failure counts, and
trace/audit degradation are measured. A human authority supplying new evidence is
credited as a legitimate recovery, not a fail-open.

## 10. Benchmark invariants (Task 15)

Fifteen invariants (B1–B15) combine runtime facts, static import analysis, and a
Strategy-D/Phase-5I equivalence check; any violation invalidates the benchmark
regardless of headline metrics. They cover identical inputs, expected-label
isolation, dataset-hash stability, Strategy-D reproduction, per-strategy provider
isolation, registry-based full composition, frozen-source non-duplication,
deterministic failures, non-applicable-not-scored, identical execution behaviour,
human-authority attribution, no cross-strategy leakage, and report reproducibility.

## 11. Reproducibility (Task 17)

One deterministic command runs all four strategies over all 90 scenarios in normal
mode plus every failure profile, checks all invariants/fairness controls, and
writes all reports. A substantive digest over scored outcomes (excluding volatile
ids/durations) is stable across repeated runs and across a clean isolated install
(`c180a0b9f0db8851…`). Optional flags: `--strategies`, `--domains`,
`--failure-profile`, `--seed`.

## 12. Packaging (Task 18)

`dgm-comparative-governance-benchmark` symlinks the canonical package, depends on
the five frozen distributions, and bundles no frozen source.
`packaging/verify_comparative_benchmark_distribution.py` builds all six wheels,
installs only the benchmark into a fresh venv (no monorepo path), and proves
import, dataset load, all strategies, Strategy-D/pilot equivalence, invariants,
fairness, report generation, and per-strategy provider isolation.

## 13. Interpretation limits

- **Deterministic reference providers are being measured.** The benchmark
  evaluates architectural behaviour and governance controls — the routing,
  gating, enforcement, verification, and fail-safe wiring — **not** production
  model/NLP accuracy (that is covered by provider conformance, which the benchmark
  consumes and does not redefine).
- **Synthetic scenario prevalence affects aggregate rates.** The `enterprise_pilot_v1`
  class mix shapes the reported rates; they are not real-world base rates.
- **Cost counts are architectural workload, not dollar cost.**
- A superior result on this benchmark does **not** prove universal superiority, and
  no production-effectiveness, regulatory-compliance, or customer-ROI claim is made.

## 14. Extension guidance

Add a strategy by implementing the `GovernanceStrategy` protocol and registering it
in `strategies/__init__.py`; keep provider imports confined to the strategy that
owns the capability (mirror `_tap_support` / `_actiongate_support`). Add a metric in
`metrics/compute.py` with an explicit denominator and a strategy-neutral definition.
Add a failure profile in `schemas/failure.py` + `failure_injection/apply.py` with an
explicit applicability rule. Never pass a scenario's expected region into strategy
code, and never regenerate or reinterpret the frozen dataset.

## 15. Headline result (this dataset)

Full governance produced **zero** unsafe outcomes; the no-governance baseline
produced **27**. Action Only prevented 21 and Assertion Only 12 — a strict subset
each, and additive: TAP and ActionGate govern disjoint failure modes (unsupported
assertions vs unsafe/out-of-envelope actions), and only the full architecture
covered both, at a measurable additional workload. See
`reports/phase6a/PHASE_6A_COMPARATIVE_BENCHMARK.md` for the full tables.
