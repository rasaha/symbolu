# Execution Eligibility — Evaluation Report

*Phases 11/13. Numbers from `execution_gate/results/evaluation.json` (deterministic, 11
scenarios, offline). Results are **conditional on the synthetic-but-real-grounded scenario
suite**; ground truth is modeled, not live-billed. The suite is deliberately built to let
the gate lose (stale-evidence and stable-environment cases included).*

## Headline table

| Baseline | success | 1st-attempt | **violation** | regret | failed-calls | abstain | latency ms | FE-crit | FI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no_eligibility | 0.545 | 0.545 | 0.182 | 0.462 | 0.273 | 0 | 786 | — | — |
| retry_only | 0.727 | 0.545 | 0.182 | 0.327 | 0.455 | 0 | 1012 | — | — |
| provider_health | 0.727 | 0.545 | 0.182 | 0.342 | 0.455 | 0 | 977 | — | — |
| static_allowlist | 0.818 | 0.636 | 0.091 | 0.164 | 0.364 | 0 | 1034 | — | — |
| **execution_gate** | 0.909 | 0.909 | **0.000** | 0.042 | **0.000** | 0.091 | 970 | **0** | 2 |
| **execution_gate + policy** | 0.909 | 0.909 | **0.000** | **0.036** | **0.000** | 0.091 | 940 | **0** | 2 |

## Primary endpoint (H1): invalid-selection rate vs retry-only

invalid-selection = policy-violation + (1 − first-attempt-success):
- retry_only: 0.182 + 0.455 = **0.637**
- execution_gate + policy: 0.000 + 0.091 = **0.091**
- **85.7% relative reduction.** H1 supported.

## Secondary endpoints

- **Policy violations: 0.182 → 0.000.** Retry-only *cannot* detect a working-but-prohibited
  provider — the call "succeeds," so it never retries. ExecutionGate excludes it up front.
  This is the single most important result: the gate prevents a class of error retry logic
  is structurally blind to.
- **Selection regret: 0.327 → 0.036 (−89%).** H2 supported.
- **Failed calls: 0.455 → 0.000.** The gate never attempts an ineligible model, eliminating
  wasted failed first-attempts (cost + latency).
- **Latency: 1012 → 940 ms.** Lower *despite* the eligibility-check overhead, because avoided
  failed-call round-trips outweigh the ~15–18 ms check cost on non-stable scenarios.
- **H3 (policy adds value post-filter):** regret 0.042 (gate) → 0.036 (gate+policy), a ~14%
  improvement. Modest but positive — ModelPolicy optimization helps *after* eligibility
  filtering, and never at the cost of a violation.

## Pre-registered operational success criteria — all met

1. violation rate 0 ✓ · 2. false-eligible-critical 0 ✓ · 3. invalid-selection ≥30% below
retry (85.7%) ✓ · 4. regret ≥30% below retry (89%) ✓ · 5. latency not exceeding saved
(940 < 1012) ✓.

## The honest costs (the gate is not free)

- **False-ineligibility (FI = 2).** In the two stale-recovery scenarios the gate degrades
  stale evidence to UNKNOWN and abstains/excludes a provider that had actually recovered —
  discarding usable (and in one case cheaper) capacity. This is why success is 0.909, not
  1.0. Mitigation is fresher probes / shorter TTLs, which cost latency and money — a real
  trade-off, not a free lunch.
- **Stable-environment overhead.** In `stable_all_ok`, everything is healthy and permitted;
  retry never retries, and the gate adds ~15–18 ms of check overhead for zero avoided
  failures. In a genuinely stable, single-provider fleet the gate is net overhead.
- **Provider-health baseline is weak** (0.727 success, 0.182 violations): coarse health
  status misses model-level, quota, residency, and policy problems — so "just add health
  checks" does **not** capture most of the value.
- **Static allowlist is the strongest baseline** (0.818 success, regret 0.164): a manual
  allowlist catches the unapproved provider but not residency/quota/model/feature failures,
  so it still carries 2× the regret and non-zero violations. Dynamic eligibility beats it,
  but the gap to a well-maintained allowlist is smaller than the gap to naive retry.

## Verdict

**Supported on this suite, conditionally.** An explicit execution-eligibility layer
delivered large, pre-registered reductions in invalid selections (−86%), policy violations
(to zero), failed calls (to zero), and regret (−89%) versus retry-only, while — critically —
committing **zero** false-eligible compliance errors. Its value concentrates exactly where
the real V1/V2 environment lived: heterogeneous multi-provider, governance-sensitive, and
unstable (quota/billing/model-availability churn). It is **marginal-to-negative** in stable,
single-provider settings, and it pays a real false-ineligibility cost under stale evidence.
The result is grounded in real failure modes but uses modeled ground truth; a live
multi-provider study (spend-capped) is the next step to confirm external validity.
