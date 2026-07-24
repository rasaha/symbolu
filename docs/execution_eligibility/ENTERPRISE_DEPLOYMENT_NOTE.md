# Enterprise Deployment Note — Execution Eligibility Layer

*Phase 13 deliverable. How the ExecutionGate + ModelPolicy layer is meant to be operated in
an enterprise multi-provider deployment, and where it does and does not pay off.*

## Where it pays off (from the evaluation)

- **Multi-provider fleets with governance constraints.** The layer's defining win is
  preventing use of a working-but-prohibited provider — a compliance breach that retry logic
  cannot detect (the call "succeeds"). Violation rate went 0.18 → 0 in evaluation.
- **Unstable provider state** — quota exhaustion, billing lapses, model renames/removals,
  regional gaps. These are exactly the failures observed live in the V1/V2 investigation. The
  gate turns "fail then fall back" into "don't attempt the doomed call": failed calls 0.45 →
  0, first-attempt success 0.55 → 0.91.
- **Cost/latency discipline at scale.** Eliminating failed first-attempts removed wasted
  round-trips; net latency fell even after check overhead.

## Where it does NOT pay off

- **Stable, single-provider deployments.** If one approved provider is always healthy, retry
  never retries and the gate is pure overhead (~15–18 ms/decision). Prefer a static config
  there.
- **When evidence is stale.** The gate is only as good as its evidence freshness. Stale
  cache caused false-ineligibility (discarding recovered capacity) in evaluation. Operators
  must tune TTLs against probe cost.

## Operating recommendations

1. **Fail-closed on governance, configurable on operations.** Keep CRITICAL-GOV conditions
   (enterprise approval, residency, region, network policy) fail-closed always. Allow
   CONDITIONALLY_ELIGIBLE for transient operational uncertainty only where the workload
   tolerates it.
2. **Right-size TTLs.** Short TTLs for volatile signals (quota, billing, reliability); long
   TTLs for stable facts (context limit, structured-output support). Stale evidence must
   degrade to UNKNOWN, never silently persist.
3. **Prefer cheap authoritative probes.** A free `models.list` or a structured error parse
   (billing/quota) is cheaper than a full inference; reserve execution-verification for
   onboarding and periodic canaries.
4. **Audit every decision.** Persist the `EligibilityDecision` (state + reason codes +
   evidence timestamps) and the ModelPolicy selection. Reason codes — not raw provider
   strings — drive dashboards and compliance reports.
5. **Budget shadow challenges.** To counter false-ineligibility, periodically probe a
   provider the gate currently excludes as recovered, so stale-negative state self-heals.

## Integration posture

Deploy ExecutionGate as an **upstream filter** in front of the existing model router. It adds
a candidate-set contract (eligible + reason-coded exclusions); the router's selection logic
is unchanged. Roll out first as **advisory/shadow** (log what it would exclude, don't
enforce) to measure false-ineligibility on real traffic before enforcing — the same
bounded-pilot posture recommended for the Model Selection Policy.
