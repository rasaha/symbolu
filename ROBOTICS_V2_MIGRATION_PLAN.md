# Robotics V2 — Naming & Production Migration Plan

**Milestone:** Robotics reliability redesign — naming review + migration.
**Depends on verdicts in:** `ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md`
(`REPLACE_ACTION_BCVF` + `AUGMENT_PREDICTOR_TRUST`).
**Constraint honored:** production paths remain **untouched** until this plan is
approved; the VC brief is **not** edited (the evidence supports a reposition,
but that is a separate, gated step).

---

## 1. Naming review

The shared "BCVF" name spans two unrelated mechanisms (`DESIGN.md:30`), plus a
third, different, LLM-origin object. This *is* a real source of confusion: a
reviewer reading "BCVF" cannot tell whether it means the action Lagrangian, the
predictor kernel, or the language-model scorer. Recommendation — name by the
**resulting architecture**, not for marketing:

| layer | current name | recommended name | rationale |
|---|---|---|---|
| action selection | BCVF action scorer | **Deterministic Robotics Decision Controller (DRDC)** | after `REPLACE_ACTION_BCVF` the layer *is* a deterministic constrained selector; the name should say so |
| predictor reliability | `bcvf_autonomous` runtime | **Predictor Trust Runtime (PTR) V2** | primary mechanism becomes innovation + EWMA/CUSUM + freshness; "trust runtime" is accurate, "BCVF" no longer is |
| the 2nd-order disagreement signal | (the whole kernel) | **BCVF retained as the name of this one internal feature** | it is a specific, real disagreement-dynamics feature; keep the name where it is technically precise |

So: **BCVF stops being a product name and becomes a feature name** — the
2nd-order disagreement detector optionally wired into PTR V2. This matches the
milestone's suggested outcome and is justified by the architecture, not by
optics.

## 2. Target architecture

```
   perception / prediction (M predictors)
              │
   ┌──────────▼───────────────────────────────────────────────┐
   │ Predictor Trust Runtime (PTR) V2   [primary, deterministic]│
   │   innovation vs robust consensus → NIS → EWMA / CUSUM      │
   │   freshness + persistent-bias + states                     │
   │     TRUSTED / DEGRADED / SUSPECT / ABSTAIN (no forced win) │
   │   [optional feature] BCVF 2nd-order disagreement → earlier │
   │     detection on accelerating/abrupt faults (delay only)   │
   └──────────┬───────────────────────────────────────────────┘
              │  per-predictor trust + system state
   ┌──────────▼───────────────────────────────────────────────┐
   │ Deterministic Robotics Decision Controller (DRDC)          │
   │   hard-invariant filter (non-compensatory)                 │
   │   → constrained / lexicographic ranking                    │
   │   → NO_SAFE_ACTION when the admissible set is empty         │
   │   + evidence/state binding, commit-time revalidation,      │
   │     hash-chained decision trace  (ActionGate architecture) │
   └──────────┬───────────────────────────────────────────────┘
              ▼  bounded, revalidated actuation command
```

## 3. Migration — action selection (`REPLACE_ACTION_BCVF`)

Staged, each stage independently revertible. **Nothing below is done until this
plan is approved.**

1. **Introduce DRDC behind a flag, dark.** Land `DeterministicDecisionController`
   (productionized `action_baselines`) next to the existing scorer; run it in
   shadow at all three call sites (`deliberative.py`, `conflict_resolution.py`,
   `task_allocation.py`), logging DRDC-vs-BCVF divergences. No behavior change.
2. **Add the hard-invariant gate first, everywhere.** Even before switching
   rankers, insert `_hard_admissible` filtering ahead of the BCVF call at sites
   1 and 2 (site 3 already pre-filters at bid intake). This closes the
   "unsafe-candidate-wins" hole immediately and is the highest-value, lowest-risk
   change.
3. **Switch ranking per call site**, deliberative → conflict → allocation, each
   gated on the shadow-divergence log showing no safe-action regressions.
4. **Wire `NO_SAFE_ACTION`** to the existing safe-state posture (stop / minimum-
   risk maneuver) at each site; verify it is reachable and correct.
5. **Adopt the three ActionGate architectural borrows** (evidence/state binding,
   commit-time revalidation, hash-chained trace) as DRDC matures.
6. **Deprecate `formulas/bcvf.py`** for action use once all three sites are
   migrated and the shadow log is clean for a release.

## 4. Migration — predictor trust (`AUGMENT_PREDICTOR_TRUST`)

1. **Land PTR V2 as the primary detector**, off the deterministic baseline
   (`predictor_trust_baseline`), in shadow against the current
   `TrustWeightComputer` on real logs; compare per the frozen metric set.
2. **Keep BCVF as an OFF-BY-DEFAULT feature.** Expose the 2nd-order signal only
   as the Fusion latency-reducer (`FusionDetector` semantics): it may lower
   detection delay on visible faults; it may **not** override an `ABSTAIN`,
   silence a `SUSPECT`, or force a winner.
3. **Do not remove the kernel.** It has a real, narrow value (faster detection
   on accelerating/abrupt disagreement) and existing tests; demote it, don't
   delete it.
4. **Add an independent reference before claiming common-mode coverage.** Both
   PTR V2 and BCVF are blind to `all_wrong`/2-of-3 `correlated_failure`; covering
   those needs a map/GNSS cross-check outside the disagreement channel.

## 5. Gating criteria before ANY production switch

* A **real-sensor pilot** (nuScenes-mini or equivalent) reproducing the
  synthetic verdicts on ≥1 real fault episode per class. The synthetic corpus
  and the 1,560-cell characterization do **not** discharge this.
* Shadow-mode divergence logs clean for one release at each call site.
* `NO_SAFE_ACTION` / `ABSTAIN` reachability and safe-state correctness verified
  in HIL.
* External review of the hard-invariant set and the ASIL/severity assignment.

## 6. What is explicitly NOT proposed

* No edit to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` until a real-sensor pilot
  supports the reposition.
* No deletion of the BCVF kernel or its tests.
* No claim that DRDC/PTR V2 is certified — this is a redesign direction backed by
  synthetic, decision-grade evidence, not a safety case.
* No proprietary formula is reproduced in any external-facing artifact; these
  docs are internal engineering records and reference code by `file:line`.

## 7. Changed-files ledger for this milestone

**Added (evaluation-only + documentation), no production path modified:**

* `robotics_reliability_bench/` — harness (baselines, detectors, corpus,
  metrics, runners).
* `ROBOTICS_BCVF_IMPLEMENTATION_AUDIT.md`, `ROBOTICS_ACTION_SELECTION_BASELINES.md`,
  `PREDICTOR_TRUST_V2_PREREGISTRATION.md`, `PREDICTOR_TRUST_FAULT_CORPUS.md`,
  `ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md`,
  `ROBOTICS_ACTIONGATE_ARCHITECTURE_MAPPING.md`, `ROBOTICS_V2_MIGRATION_PLAN.md`.
* `robotics_reliability_bench/results/*.json` — machine-readable outputs.

**Modified production code:** none (per milestone constraint — keep production
paths untouched until the benchmark produced a verdict; it now has).
