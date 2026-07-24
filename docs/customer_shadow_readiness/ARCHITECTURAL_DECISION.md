# Architectural Decision (M12)

*Decided against the eligibility gate (`PILOT_ELIGIBILITY_AND_PLAN.md`) and the readiness assessment
(`PRODUCT_READINESS_ASSESSMENT.md`). One of ten options.*

## The ten options

| # | Option | Verdict |
|---|---|---|
| 1 | **READY FOR BOUNDED CUSTOMER SHADOW PILOT** | **Chosen (with scoped conditions)** |
| 2 | Ready for single-tenant internal pilot only | documented fallback |
| 3 | Fix ActionGate integration first | **No** — Gap 0 cleared (0 unsafe disagreement) |
| 4 | Fix security or tenant isolation first | **No** — fail-closed boundary + isolation hold under load |
| 5 | Fix data-handling controls first | **No** — classification/redaction/retention/erasure in place |
| 6 | Fix observability or incident controls first | **No** — metrics + alerts + detection→kill + runbook |
| 7 | Fix human-review workflow first | **No** — tenant-scoped queue, no silent override |
| 8 | Fix deployment or rollback first | **No** — pinned non-enforcing manifest + verified rollback |
| 9 | Not enough evidence | **No** — differential study, fault sweep, load test, eligibility gate |
| 10 | Do not proceed | **No** — no blocker found |

## Decision: Option 1 — READY FOR BOUNDED CUSTOMER SHADOW PILOT (scoped)

Proceed to a **bounded, non-enforcing customer shadow pilot** under the scoped conditions below. The
eligibility gate passes all six fail-closed conditions, and the principal limitation (Gap 0) is resolved:
the real ActionGate is integrated read-only and introduces **no unsafe disagreement** with the prior
shadow mapping — it is, if anything, stricter and richer.

### Separated dimensions (each judged on its own evidence)

- **Architectural viability:** READY — inherited from the frozen pilot, unchanged.
- **Safety:** READY (shadow) — pilot 0 unsafe escape; real ActionGate stricter than the shadow mapping;
  every operational fault fails closed; no path enforces.
- **Utility:** demonstrated on structured cases (0 false-block); real-traffic utility is what the pilot
  gathers.
- **Latency / cost:** governance overhead sub-millisecond and ~$0; the real barrier (model call) is out
  of scope.
- **Explainability:** READY — audit trace + replay + tenant-scoped review + reason codes.
- **Operational maturity:** LIMITED — real controls, shadow-grade (in-memory, stubbed KMS/IdP, no
  external observability).
- **Customer-pilot readiness:** READY (bounded, conditioned).
- **Production readiness:** NOT READY — real IdP/KMS/deploy/model-latency NOT EVALUATED.

### Scoped conditions (binding)

1. **De-identified / explicitly-permitted data only.** Secrets/KMS and IdP are shadow-grade stubs; real
   KMS + real IdP are prerequisites for non-de-identified data.
2. **Real ActionGate vocabulary extension tracked.** Log the real 6-value outcome alongside the mapped
   disposition so the 25% semantic loss never reaches the audit; extend the runtime vocabulary before the
   real gate replaces the shadow mapping in the enforcing path (which does not exist in a shadow pilot).
3. **Bounded shape, no expansion without re-gating.** More tenants, enforcement, or live model calls each
   require a fresh readiness pass.
4. **Non-enforcing, no external actions, no live provider calls, no real customer onboarding.**

### Documented fallback

If a reviewer weights the shadow-grade authn/secrets as insufficient for *external* exposure, fall back
to **Option 2 (single-tenant internal pilot)** — the identical runtime restricted to an internal tenant —
while the real IdP/KMS are built. The eligibility evidence supports both; Option 1 is the recommendation
because tenant isolation is demonstrably sound (including under concurrent load) and the pilot is
non-enforcing on de-identified data.

## One-line statement

> Ready for a bounded, non-enforcing customer shadow pilot on de-identified data: Gap 0 is cleared (real
> ActionGate integrated read-only, zero unsafe disagreement), the eligibility gate passes all six
> fail-closed conditions, and tenant isolation holds under load — with real IdP/KMS/observability/deploy
> and the ActionGate vocabulary extension as tracked prerequisites before scaling or production.
