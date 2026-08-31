# End-to-End Evaluation Report (v1)

*Phase 17. The 30-trace dataset run through all eight baselines (Phase 10). Deterministic;
SHADOW/MOCK; no live calls; no real actions. Results separated by evidence tier; no blended
headline number (Phase 2 rule). Raw: `control_plane_shadow/eval_results/end_to_end_v1.json`
(regenerate: `python3 -m control_plane_shadow.baselines`).*

## Baseline results (30 traces)

| Baseline | Architecture | Expected-match | Unsafe-transition | Sel-outside-eligible | Ungoverned actions | Governance skipped |
|---|---|---|---|---|---|---|
| 1 glue | informal glue (no versions, no invariants) | 0.90 | **0.0** | 0 | 0 | 0 |
| 2 script | sequential, no contracts | 0.90 | **0.0** | 0 | 0 | 0 |
| 3 contracts | versioned contracts only | **1.0** | **0.0** | 0 | 0 | 0 |
| 4 contracts+inv | contracts + invariant enforcement | **1.0** | **0.0** | 0 | 0 | 0 |
| 5 unified | unified control plane, real adapters | **1.0** | **0.0** | 0 | 0 | 0 |
| 6 unified+telemetry | unified + shadow telemetry | **1.0** | **0.0** | 0 | 0 | 0 |
| 7 two-gate | ExecutionGate + ActionGate only | 0.47 | 0.067 | 0 | 0 | 27 |
| 8 router | ModelPolicy + retry only | 0.37 | **0.30** | 1 | 8 | 30 |

## Preregistered endpoints (unified, baseline 5) — TIER-separated

| Endpoint | Threshold | Result (TIER) | Pass |
|---|---|---|---|
| semantic contract preservation | ≥ 0.95 | 1.0 (T3 governance) | ✅ |
| unsafe transition rate (co-primary) | == 0.0 | 0.0 | ✅ |
| adapter normalization accuracy | ≥ 0.95 | 1.0 (T3) | ✅ |
| reason-code completeness | == 1.0 | 1.0 | ✅ |
| trace completeness | == 1.0 | 1.0 | ✅ |
| audit-chain completeness | == 1.0 | 1.0 | ✅ |
| selection-eligibility consistency | == 1.0 | 1.0 | ✅ |
| fallback re-entry correctness | == 1.0 | 1.0 (T2 provider) | ✅ |
| assertion/action separation | == 1.0 | 1.0 | ✅ |
| unauthorized action propagation | == 0.0 | 0.0 (T1 exec) | ✅ |
| false blocking | == 0.0 | 0.0 | ✅ |
| indeterminate propagation correctness | == 1.0 | 1.0 | ✅ |
| version-mismatch detection | == 1.0 | 1.0 | ✅ |
| partial-degradation safety | == 1.0 | 1.0 | ✅ |
| replay determinism | == 1.0 | 1.0 | ✅ |
| component-call overhead vs glue | ≤ 1.25× | ~1.0× (same adapters) | ✅ (reported) |
| p50 / p95 latency | reported | 1.25 / 3.81 ms **deterministic-local, NOT production** | — |

**All gated endpoints pass for the unified baseline.** The governance dispositions are TIER 3
(real engines); fallback/provider are TIER 1–2; the TAP semantic-gap caveat applies to the
assertion-governance interpretation (the *transmission* fidelity is 1.0, the *interpretation* is
an approximation).

## Which layers are load-bearing

- **ExecutionGate — load-bearing.** Baseline 8 (no ExecutionGate) selects outside the eligible
  set (1 trace) because selection is never constrained by eligibility. The ExecutionGate→
  ModelPolicy structural constraint is what prevents this.
- **ModelPolicy — load-bearing for quality.** Baseline 7 (no ModelPolicy) picks an arbitrary
  first-eligible model; utility optimization is lost (not a *safety* failure, a *quality* one).
- **TAP / assertion governance — load-bearing (with semantic-gap caveat).** Baseline 7 (no TAP)
  delivers ungoverned assertions on the 2 traces that should REJECT/ESCALATE → 6.7% unsafe. The
  assertion boundary matters; that E4 is an *approximate* assertion governor is the standing gap.
- **ActionGate — load-bearing.** Baseline 8 (no ActionGate) lets 8 action traces reach the runtime
  ungoverned → 30% unsafe. Action governance is the largest single safety contributor here.
- **Contracts (version validation) — load-bearing for version correctness.** glue/script (0.90)
  vs contracts (1.0): the only difference is that version validation correctly REJECTS the 3
  version-mismatch traces. This matches the prior track: contracts add *version* safety.
- **Invariant enforcement — NO measurable delta on this dataset (honest negative).** Baselines 3
  (contracts only) and 4/5 (contracts + invariants) are identical: 1.0 match, 0.0 unsafe. Because
  the real adapters enforce the eligibility constraint *structurally* (ModelPolicy only sees the
  eligible registry) and the orchestrator fail-closes on governance regardless of the flag, the
  invariant-enforcement flag catches nothing extra here. The bypass it *would* catch is exactly
  what baseline 8 exhibits by removing the structural constraint — so the load-bearing element is
  the **structural eligibility gate**, not the enforcement flag.

## Answering the primary research question

> Can the real components exchange information through the canonical contracts without semantic
> loss, authority leakage, unsafe bypass, trace incompleteness, or excessive overhead?

**On this dataset, in SHADOW/MOCK: yes.** The unified baseline preserves semantics (fidelity
1.0), leaks no authority, produces zero unsafe transitions, completes every trace's audit, and
adds negligible component-call overhead — while the crippled baselines (7, 8) demonstrate that
the eligibility gate, assertion governance, and action governance are each individually load-
bearing. The one honest qualifier beyond the tier ceilings: **invariant *enforcement* adds no
measurable value on top of the structural constraints on this dataset** — the value lives in the
structure (the gates themselves), consistent with the prior mock track.

## What this does NOT show

No live execution, no production latency, no commercial claim. "Assertion governance validated"
is still **not** licensed (TAP semantic gap). The dataset is falsifying, not exhaustive (30
traces). Evidence ceiling is TIER 3.
