# Pilot Eligibility Gate & Bounded Shadow-Pilot Plan (M12)

*`customer_shadow_readiness/eligibility.py`. A single fail-closed gate that aggregates the readiness
conditions, plus the plan for a bounded customer shadow pilot.*

## Eligibility gate (fail-closed — ALL must hold)

| Condition | Check | Result |
|---|---|---|
| Gap 0 — ActionGate, no unsafe disagreement | differential study: shadow-blocks/real-allows == 0, real gate deterministic | **PASS** |
| Security & tenant isolation | valid submit; cross-tenant denied; no-token denied | **PASS** |
| Data-handling controls | clearance lattice denies restricted-under-internal; redaction works | **PASS** |
| Kill switches | pilot kill halts the runtime | **PASS** |
| Operational faults fail closed | all 10 operational faults fail closed, none enforced | **PASS** |
| Deployment & rollback | preflight deployable (enforcement off + artifacts intact); rollback safe | **PASS** |

**Result: ELIGIBLE FOR BOUNDED CUSTOMER SHADOW PILOT = True.** Every condition is a concrete check, not
an assertion; the gate is fail-closed (one failure → not eligible).

## Bounded customer shadow-pilot plan

**Shape:** 1–3 tenants, de-identified / explicitly-permitted artifacts only, issued pilot tokens,
shadow-only (`WOULD_*` dispositions), **no enforcement, no external actions, no live provider calls**.

**Per-tenant setup:** issue scoped tokens (`shadow:submit`, `shadow:review`); set the tenant clearance
and retention policy; enable the tenant kill switch control; register reviewers.

**Runtime:** requests flow through `pilot_api.submit` (kill → auth → tenant scope → secure intake →
read-only orchestrator → minimized/redacted trace). The **real ActionGate** decides action proposals
read-only (M2/M3). Dispositions and redacted traces are logged; escalations route to the tenant-scoped
review queue.

**Monitoring:** per-tenant metrics + alerts (M7); SEV1 isolation/safety signals auto-trip the tenant or
pilot-wide kill.

**Exit criteria:** the pilot ends (per-tenant or pilot-wide) on any SEV1 that cannot be root-caused, on
a rollback to the frozen baseline, or on schedule. Rollback is the verified 4-step procedure (M8).

**Success signals to gather (what the pilot converts from PARTIAL to evidence):** real-traffic
disposition mix, false-block on genuine clean requests, reviewer agreement/override on real cases,
observed latency with real data, and any real-ActionGate vocabulary-loss impact.

## Scoped conditions on the eligibility

The gate certifies readiness for a **bounded** pilot under these hard conditions:

1. **De-identified / permitted data only** — the secrets/KMS and IdP are shadow-grade stubs (M4/M5);
   non-de-identified customer data requires a real KMS + real IdP first.
2. **Real ActionGate vocabulary extension** — the 25% semantic loss (M3) is a tracked integration
   refinement; the pilot logs the real 6-value outcome alongside the mapped disposition so no information
   is lost in the audit even before the runtime vocabulary is extended.
3. **No expansion beyond the bounded shape without re-gating** — more tenants, enforcement, or live model
   calls each require a new readiness pass.

If a reviewer weighs the shadow-grade auth/secrets as insufficient for *external* exposure, the
documented fallback is a **single-tenant internal pilot** (Option 2) — same runtime, internal tenant
only — while the real IdP/KMS are built.
