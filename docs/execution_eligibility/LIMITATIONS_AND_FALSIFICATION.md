# Limitations and Falsification Report

*Phase 11/13. Each pre-registered falsification target (Phase 10) is answered against the
measured results. Null and negative findings are reported directly, not reframed.*

## Falsification targets — measured verdicts

| Target (the layer is falsified/weakened if…) | Measured result | Verdict |
|---|---|---|
| ordinary retry logic performs as well | retry invalid-selection 0.637 vs gate 0.091; retry commits 0.18 violations, gate 0 | **Not falsified** — retry is structurally blind to working-but-prohibited providers |
| provider-health checks provide nearly all the value | provider_health = 0.727 success, 0.182 violations (≈ retry) | **Not falsified** — coarse health misses model/quota/residency/policy |
| eligibility checks add too much latency | gate 940 ms < retry 1012 ms | **Not falsified** — avoided failed calls outweigh check overhead |
| cached eligibility goes stale too quickly | stale evidence caused **FI = 2** (false-ineligibility) | **Partially confirmed** — staleness is the gate's real weakness; TTL tuning is load-bearing |
| false ineligibility removes useful capacity | success 0.909 < 1.0 precisely because of 2 stale-recovery misses | **Confirmed as a real cost** — bounded here, but non-zero |
| live probes create excessive cost | offline; probe cost modeled as ~15–18 ms; live cost unmeasured | **Open** — requires the live study |
| network reachability dominates all signals | violations (governance) and quota/model failures each drove distinct wins; no single signal dominated | **Not falsified** — value is distributed across conditions |
| billing/quota checks too provider-specific | normalized into provider-neutral reason codes; replay covered Google free-tier + others | **Not falsified** — normalization held across providers |
| manual allowlists outperform dynamic discovery | static_allowlist is the *best baseline* (0.818, regret 0.164) but still 0.091 violations + 4.5× gate regret | **Not falsified, but narrowed** — a good allowlist closes much of the gap |
| ModelPolicy adds nothing after eligibility filtering | regret 0.042 (gate) → 0.036 (gate+policy), ~14% | **Weak positive** — small but non-zero benefit |
| ExecutionGate benefits vanish in stable environments | `stable_all_ok`: gate adds overhead, zero avoided failures | **Confirmed** — null/negative in stable single-provider settings |
| operational complexity exceeds the benefit | large primary-endpoint gains on the realistic multi-provider mix; overhead only in stable case | **Not falsified for heterogeneous fleets; falsified for stable ones** |

## Limitations

1. **Modeled ground truth.** Outcomes are synthetic (grounded in real V1/V2 failure modes
   but not live-billed). External validity requires a live, spend-capped multi-provider run.
2. **Small, hand-built suite (11 scenarios).** Deliberately spans the failure taxonomy and
   includes cases where the gate loses, but it is not a probability-weighted sample of real
   traffic. Aggregate metrics depend on the scenario mix; a stable-heavy fleet would shift
   the verdict toward "overhead."
3. **Staleness is the dominant risk.** The gate's correctness is bounded by evidence
   freshness; the false-ineligibility cost is real and TTL-sensitive. This is the first thing
   a live study must characterize.
4. **Reference ModelPolicy is intentionally simple.** The scientific selection engine is the
   frozen Model Selection Policy; this track's ModelPolicy is a thin utility selector to
   demonstrate the contract, not to re-litigate routing quality.
5. **Provider-specific probe adapters not built for live use.** The evaluation uses mock
   adapters and replay evidence; real billing/quota/model probes per provider are future work
   (deliberately, to keep the unit-test suite credential-free).
6. **Single-request evaluation.** No cross-request telemetry feedback loop is exercised
   (registry-update-from-telemetry is specified but not stress-tested under drift).

## Honest bottom line

The execution-eligibility layer adds **measurable, pre-registered value** on the exact
conditions the real investigation exhibited — multi-provider heterogeneity, governance
constraints, and quota/billing/model-availability churn — chiefly by preventing compliance
violations retry logic cannot see and by not attempting doomed calls. It is **not**
universally beneficial: in stable single-provider settings it is overhead, and under stale
evidence it discards usable capacity. The correct framing is a **conditional, environment-
dependent** benefit, deployed advisory-first, with a live spend-capped study as the next step
to establish external validity.
