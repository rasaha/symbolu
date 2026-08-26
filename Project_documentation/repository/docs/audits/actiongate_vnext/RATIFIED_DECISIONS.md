# ActionGate vNext — Ratified Decisions

**Date:** 2026-08-26
**Scope:** Clock authority for replayed scenarios. No ActionGate policy semantics
are changed here, and CABP is out of scope.

---

## D1 — The scenario clock is authoritative for a replayed scenario

**Decision `[R]`:** A replayed scenario has exactly one time domain: the frozen
scenario clock the run's DGM services are built from. Every collaborator that
stamps or compares a time within that run — the CER binding service, the
execution adapter, and the ActionGate control-plane adapter alike — must read
that clock. The wall clock is not a permitted source of time inside a replay.

**Consequence:** `ActionGovernanceControlPlaneAdapter`'s default
(`_default_clock` → kernel `utc_now`) is correct for live operation and wrong
for every replay harness. Harnesses must inject the clock explicitly; the
default is never the right answer inside one.

**Rationale:** the value being compared is the run's own CER expiry, which the
run itself minted on the frozen clock. Comparing it against the wall clock
compares two unrelated instants, and makes a replay's verdict a function of the
calendar date the suite happens to run on. Determinism is the point of the
harness.

---

## Regression found while settling these items

**`[V]` Symptom.** 84 tests failed across `enterprise_validation_pilot`,
`comparative_governance_benchmark` and `provider_heterogeneity_validation`.

**`[V]` Cause.** Those harnesses build their CER on a frozen scenario clock
(`make_clock` → 2026-01-01T00:00:00Z, so `expires_at` is 2026-01-01T01:00:00Z)
while constructing `ActionGovernanceControlPlaneAdapter` with its default wall
clock — e.g. `provider_heterogeneity_validation/runners/workflow.py:149`. The
adapter stamps `authorized_at = now_wall` and `expires_at = now_wall +
validity`; `ExecutionService.create_execution_intent` then compares that stamp
against the scenario clock and raises `AuthorizationExpiredError`
(`packages/capabilities/decision-authority/src/ugence_decision_authority/services/execution_service.py:129`).

**`[V]` Latency of the fault.** The failure is date-dependent, not
deterministic: it appears whenever the wall clock sits on the wrong side of the
scenario clock. Reproduced by pinning the wall clock to 2025-06-01 — 62 failures
in the pilot, a collection-time error in the benchmark, 3 in heterogeneity
validation.

**`[V]` Resolution.** Under D1, the scenario clock is injected at all three
adapter construction sites: `enterprise_validation_pilot/composition/root.py`,
`comparative_governance_benchmark/strategies/_actiongate_support.py` (the seed
now flows in from `strategies/action_only.py`), and
`provider_heterogeneity_validation/runners/workflow.py`. ActionGate policy
semantics are untouched.

**`[V]` Guard.** Each tree carries `tests/test_clock_domain.py`, which fails if
a harness mixes the domains again: an AST scan rejecting any
`ActionGovernanceControlPlaneAdapter(...)` site in that tree without a `clock=`
argument, and a replay that moves the adapter's default wall clock and asserts
every substantive outcome is unchanged. Both fail when the injection is removed.

**`[V]` State.** 277 tests pass across the three trees (271 pre-existing, 6 new
guards), with the wall clock at its true value and at the skewed value that
originally reproduced the regression.
