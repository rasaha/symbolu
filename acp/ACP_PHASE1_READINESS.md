# ACP Phase 1 — Readiness & Scope

Phase 0 froze the envelopes, interfaces, identity, fail-closed selection, trace,
and failure-state scaffolding. **Phase 1 is NOT implemented in this milestone.**
This document specifies it.

---

## 1. Phase 1 objective

Wire the deterministic hard-admissibility path into a **shadow** comparison
against the current BCVF action call sites — without changing production
behaviour — proving ACP would make safe, explainable decisions where BCVF
currently can rank an unsafe action.

## 2. Phase 1 scope (in order)

1. **Hard-admissibility filter (real constraints).** Implement a
   `HardConstraintEvaluator` backed by the existing deterministic safety modules
   (`safety/collision_guard.py`, `constraint_monitor.py`, `human_proximity.py`,
   `energy_bounds.py`, `trajectory_validator.py`) — KEEP components from the
   reuse audit. Map each to a typed `ConstraintResult`.
2. **Candidate rejection with dispositive reasons.** Produce a `DecisionTrace`
   per candidate set showing the first violated hard constraint per rejected
   candidate.
3. **`NO_SAFE_ACTION` wiring (shadow only).** When the admissible set is empty,
   emit `NO_SAFE_ACTION` into the trace sink; do **not** yet drive the runtime.
4. **Deterministic selection among survivors.** Use `DeterministicActionSelector`
   with a real `SoftObjective` calibrated to the deployment; total tie-break.
5. **Shadow comparison harness.** At each of the three BCVF call sites, run ACP
   alongside the live BCVF scorer on the same candidate set; log every
   divergence (ACP-refuses-vs-BCVF-picks, different winner, ACP-admits-only-safe)
   to an artifact. **The live decision remains BCVF's**; ACP is observe-only.

## 3. Explicit Phase 1 exclusions

- No production call-site switch (that is Phase 2).
- No predictor-trust replacement (Phase 3).
- No execution authorization on the live path (Phase 4).
- No removal of `formulas/bcvf.py` (Phase 5).

## 4. Entry criteria (met by Phase 0)

| criterion | status |
|---|---|
| Frozen canonical envelopes | ✅ |
| Deterministic identity + tests | ✅ |
| Fail-closed selector with `NO_SAFE_ACTION` / `REQUEST_MORE_OBSERVATION` | ✅ |
| Structured decision trace | ✅ |
| Failure-state scaffolding | ✅ |
| Zero current-runtime behaviour change | ✅ |
| No production ACP call sites | ✅ (grep-asserted) |

## 5. Exit criteria for Phase 1

- Real `HardConstraintEvaluator` covering the KEEP safety modules, with tests.
- Shadow harness at all three BCVF sites emitting a divergence log.
- A report quantifying, on recorded scenarios, how often ACP would have refused
  an action BCVF ranked into the winning slot — **without** any production
  behaviour change.
- Preregistered `SoftObjective` weights + tie-break profile (mirroring the
  prior milestone's preregistration discipline) before any Phase 2 switch.

## 6. Open items carried from architecture (unchanged by Phase 0)

D1 common-mode reference source, D2 constraint-completeness HARA, D3 WCET
measurement, D4 real-time port — all remain gating for a *production* switch and
are untouched by Phase 0/1 shadow work.
