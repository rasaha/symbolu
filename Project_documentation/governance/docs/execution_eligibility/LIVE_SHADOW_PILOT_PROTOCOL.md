# Live Shadow-Pilot Protocol (pre-registered)

*Phases 3–7, 9–11. A NEW protocol, separate from and not reusing replay_v1 as fresh
evidence. No live paid execution begins under this document; it defines what a live study
would do. Live calls require explicit authorization + present credentials + spend controls.*

## Phase 3 — Primary research question

**Can ExecutionGate accurately predict real provider-model-request executability *before*
execution — reducing failed first attempts and policy-invalid selections without excessive
latency, probe cost, or false exclusion?**

The pilot evaluates *predictions*; it does **not** initially control production routing.
Normal routing stays authoritative; ExecutionGate runs in **shadow mode**, recording what it
*would have* allowed, excluded, or marked indeterminate.

## Phase 4 — Pre-registered endpoints

**Primary endpoint:** **false-eligible rate** — the fraction of candidates predicted ELIGIBLE
that, when actually attempted, fail or violate a critical policy condition. Critical (compliance)
false-eligibility is reported **separately** from operational failures and must be ~0.

**Secondary endpoints:** eligibility precision; eligibility recall; false-ineligible rate;
indeterminate rate; first-attempt-success prediction accuracy; invalid-selection avoidance;
failed-call avoidance; policy-violation avoidance; stale-evidence error rate; time-to-detect
provider degradation; time-to-detect provider recovery; eligibility-check overhead; p50/p95
added latency; probe cost; cost per avoided failed call; quota consumed by probes; registry-state
drift; reason-code accuracy; ModelPolicy incremental regret reduction *after* eligibility filtering.

A provider that executes technically but violates residency/enterprise policy/another critical
rule counts as **false-eligible** if the gate allowed it.

## Phase 5 — Shadow labels (prediction and observation kept independent)

**Prediction (before execution):** ELIGIBLE | INELIGIBLE | CONDITIONALLY_ELIGIBLE |
INDETERMINATE; emitted reason codes; evidence timestamps; evidence age; policy version;
registry version.

**Observed outcome (after normal execution or controlled validation):** SUCCESS | AUTH_FAILURE |
NETWORK_FAILURE | QUOTA_FAILURE | BILLING_FAILURE | MODEL_UNAVAILABLE | FEATURE_MISMATCH |
CONTEXT_FAILURE | POLICY_PROHIBITED | RESIDENCY_PROHIBITED | TIMEOUT | PROVIDER_ERROR |
INVALID_RESPONSE | NOT_ATTEMPTED | UNKNOWN.

**The prediction is never derived from the observation.** They are captured in separate,
append-only records and joined only at analysis time.

## Phase 6 — Ground-truth rules (live outcome → label)

- successful valid inference under applicable policy → **operationally executable**.
- 401/403 auth error → **not executable** (AUTH_FAILURE).
- network/proxy denial → **not executable** (NETWORK_FAILURE).
- quota exhaustion → **temporarily not executable** (QUOTA_FAILURE).
- provider timeout above the frozen limit → **not executable for that policy window** (TIMEOUT).
- model not found → **not executable** (MODEL_UNAVAILABLE).
- successful inference from a prohibited provider → **technically executable but
  policy-ineligible** (POLICY_PROHIBITED / RESIDENCY_PROHIBITED) → counts as false-eligible if allowed.
- no actual attempt → **NOT_ATTEMPTED**; outcome remains *unverified* — never presumed success
  or failure.

**Precedence for conflicting evidence:** critical policy/compliance evidence **overrides**
operational success (a prohibited-but-working model is ineligible, not eligible). A model is
**never** labeled execution-verified from enumeration alone — only a successful real inference (or
an explicitly-allowed provider-authoritative equivalent) qualifies.

## Phase 7 — Two-stage design

**Stage A — controlled connectivity calibration:** minimal synthetic probes only, **no customer
content**; verify provider access, latency, quota, billing, response validity; measure probe
overhead; estimate signal TTL behavior; validate audit logging and spend enforcement.

**Stage B — advisory shadow traffic:** ExecutionGate observes real routing contexts; the normal
router stays authoritative; **no hard blocking**; **no partner data sent to an additional provider
solely for evaluation**; compare gate predictions against outcomes already produced by normal
execution; controlled counterfactual probes only where policy/consent/privacy/spend explicitly
allow. **Enforcement is out of scope for this track.**

## Phase 9 — TTL & staleness study (prospective; exploratory / separately versioned)

Staleness was replay_v1's dominant limitation. TTL is calibrated **prospectively** — the winning
TTL is **not** chosen from replay_v1. Candidate TTL policies, defined in advance:
fixed-short | fixed-medium | fixed-long | reason-code-specific | event-triggered-invalidation |
provider-health-assisted | conservative-fail-closed-expiry.

Measured: stale false-eligibility; stale false-ineligibility; probe frequency; probe cost;
detection lag; recovery lag; capacity lost to conservative expiry. This is **exploratory** or a
separately versioned study; replay_v1 is not reused as confirmatory evidence.

## Phase 10 — Live baselines (pre-registered; frozen before outcome inspection)

1. normal routing, no eligibility layer; 2. retry-only; 3. static allowlist;
4. provider-health-only; 5. cached ExecutionGate; 6. live-probe-assisted ExecutionGate;
7. ExecutionGate + ModelPolicy. **ModelPolicy is evaluated only after eligibility filtering.**
No baseline is added or removed after outcome inspection.

## Phase 11 — Sample size and stopping

No large confirmatory sample is invented without variance information.

**Stage A minimum:** enough controlled probes to verify every configured provider-model binding
and every major operational reason-code class reachable in the environment.

**Stage B development window:** a fixed initial observation count *or* fixed time window, used to
estimate event prevalence and variance — **not** treated as confirmatory unless explicitly
pre-registered as such.

Specify per run: minimum observations; minimum failure-state transitions; minimum provider-recovery
events (where observable); spend cap; max probe count; max quota consumption; max added latency;
early-stopping for safety/cost; **termination if critical logging or privacy controls fail**.

**If live failure events are too rare for powered inference, report UNRESOLVED — do not
manufacture incidents.**

## Relationship to replay_v1

replay_v1 is frozen prior context. This live protocol is a distinct, prospective study. Its results
will be versioned as `live_shadow_v1` (or similar), never merged into or used to re-interpret
replay_v1.
