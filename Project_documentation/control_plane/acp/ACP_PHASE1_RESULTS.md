# ACP Phase 1 — Results & Verdicts

**Run:** deterministic shadow benchmark over the frozen corpus (14 classify + 2
authorization scenarios, all synthetic). Machine-readable:
`robotics_reliability_bench/results/acp_shadow_results.json`. Preregistration:
`ACP_PHASE1_PREREGISTRATION.md` (committed `975c266`, before this run).
**Shadow-only. Production BCVF remained authoritative. Zero production edits.**

---

## 1. Headline metrics (overall, 14 candidate sets)

| metric | value |
|---|---|
| sets evaluable by ACP | 100% |
| deterministic-rerun identity | **100%** |
| current-runtime behavior-change count | **0** |
| agreement (both pick same admissible) | 0.50 (7/14) |
| **BCVF selected an ACP-inadmissible candidate** | **0.357 (5/14)** |
|   — of which **REAL hard-constraint violation** | **3** |
|   — of which merely unevaluable (no/missing data) | 2 |
| ACP returned NO_SAFE_ACTION | 1/14 |
| both admissible, different pick | 2/14 |
| authorization revalidation (stale + modified) | **both rejected** |
| mean ACP latency | ~0.07 ms/set |

## 2. Per-scenario outcome

| site | scenario | BCVF pick | ACP pick | class |
|---|---|---|---|---|
| deliberative | clear safe winner | move | move | AGREE |
| deliberative | unsafe move (obstacle 0.3 m) | move | wait | **BCVF_INADMISSIBLE · REAL_VIOLATION** |
| deliberative | missing obstacle evidence | move | wait | BCVF_INADMISSIBLE · UNEVALUABLE |
| deliberative | grasp (unevaluable here) | grasp | wait | BCVF_INADMISSIBLE · UNEVALUABLE |
| deliberative | only wait | wait | wait | AGREE |
| conflict | stop vs efficient | RESOURCE | MUTUAL_STOP | DIFFERENT_BOTH_ADMISSIBLE |
| conflict | unsafe strategy present | RISKY (safety 0.3) | SPATIAL | **BCVF_INADMISSIBLE · REAL_VIOLATION** |
| conflict | all unsafe, no stop | RESOURCE | — (NO_SAFE_ACTION) | **BCVF_INADMISSIBLE · REAL_VIOLATION** |
| conflict | safety fallback only | MUTUAL_STOP | MUTUAL_STOP | AGREE |
| conflict | exact tie | A | A | AGREE |
| task_alloc | closest capable | r_close | r_close | AGREE |
| task_alloc | both admissible disagree | r_b | r_a (closer) | DIFFERENT_BOTH_ADMISSIBLE |
| task_alloc | incompatible bid | r_ok | r_ok | AGREE (r_lowcap rejected) |
| task_alloc | exact tie | r_a | r_a | AGREE |

## 3. Per-call-site reading

- **Deliberative (3/5 BCVF-inadmissible).** BCVF selects a candidate ACP rejects
  60% of the time here — one a **real** obstacle-clearance violation, two
  unevaluable (missing obstacle data; grasp has no hard-constraint data at this
  site). ACP falls back to `wait` (safe fallback) every time it refuses a motion.
  Highest-signal site, but two of the three are *unevaluable*, not proven-unsafe.
- **Conflict resolution (2/5 real violations + 1 informative disagreement).**
  BCVF picks the low-safety `RISKY` strategy and, in the all-unsafe set, a
  strategy ACP rejects — both **real violations** ACP catches. The
  stop-vs-efficient set reproduces the known pathology: BCVF's consistency term
  demotes the safest `MUTUAL_STOP`; ACP's `safety_score ↓` order selects it.
  Cleanest per-candidate safety data of the three sites.
- **Task allocation (0 violations, 3/4 agree).** ACP's hard filter **duplicates**
  the existing intake pre-filters, so all bids reaching the decision are already
  admissible; ACP's only distinct effect is a different selection rule
  (closest/least-loaded vs BCVF). Lowest incremental value at the hard-filter
  layer.

## 4. Success criteria (all met — see preregistration §6)

1. rerun identity 100% ✓  2. ACP never selected an inadmissible candidate ✓
3. advisory can't override a hard failure ✓  4. missing evidence never `EXECUTE`
✓  5. stale/modified authorization rejected ✓  6. behavior-change count 0 ✓
7. ≥1 real call site with adequate adapter coverage (conflict_resolution) ✓.
Tests: **55 ACP tests pass** (pytest + unittest); robotics baseline unchanged.

## 5. Limitations (binding)

- **Synthetic corpus only.** No real-scenario or real-sensor data. Rates are
  illustrative of the *mechanism*, not field frequencies. No real-sensor safety
  claim is made.
- **Core physical constraints UNAVAILABLE at every call site** (collision margin
  in metres, stopping distance, actuator limits, stability). The hard filter
  runs on the abstract/operational data the sites happen to carry. This is the
  main reason the logic verdict is *WITH_LIMITATIONS*.
- **Some candidate classes are unevaluable** (deliberative grasp/release) — ACP
  fails closed on them rather than judging them.
- **Task-allocation hard filter is redundant** with existing pre-filters.
- **Parent-package import caveat:** ACP module sources are stdlib-only, but
  importing them via the package path runs `symbolu_robotics/__init__.py`, which
  eagerly imports numpy + the BCVF re-export. A property of the existing parent
  package, not of ACP; no effect on determinism or production behavior.

## 6. Verdicts

### Hard-admissibility logic → **`HARD_FILTER_SUPPORTED_WITH_LIMITATIONS`**
Every call site has ≥1 non-fabricated hard constraint; ACP never selected an
inadmissible candidate; determinism is 100%; fail-closed holds. BUT the core
physical constraints are UNAVAILABLE at all three sites, some candidate classes
are unevaluable, and the task-allocation filter merely duplicates existing
pre-filters. Supported, with clearly-scoped limitations.

### Production migration readiness → **`READY_FOR_GATED_CANARY`** (narrowly scoped)
All six gating conditions in the preregistration/milestone are literally met
(zero behavior change, 100% rerun identity, never selects inadmissible, adequate
coverage for ≥1 real site, missing-evidence fail-closed, no real-sensor claim).

**Scope and sequencing (recommended, not optional):**
- The canary is permissible **only at `conflict_resolution`** — the site with
  genuine per-candidate safety data, full adapter coverage, and a clear
  safety-first benefit (rejecting low-safety strategies; preferring `MUTUAL_STOP`).
- **`SHADOW_CONTINUE` for `deliberative`** until real obstacle/world data is
  wired (two of its three refusals are *unevaluable*, not proven-unsafe), and
  **for `task_allocation`** (hard filter redundant; low value).
- Before any canary: one **real-scenario shadow-logging cycle** (non-synthetic),
  a reversible default-OFF flag, BCVF retained as the live fallback, and **no
  actuation** through ACP without explicit, human-configured enablement.
- Full replacement remains out of scope (Phase 1 rule).

## 7. Phase 2 recommendation

1. Wire the real `safety/` modules (`collision_guard`, `trajectory_validator`,
   `constraint_monitor`, `energy_bounds`, `human_proximity`) into a
   `HardConstraintEvaluator` so the UNAVAILABLE physical constraints become
   available — the single highest-value gap.
2. Run a real-scenario shadow-logging cycle at `conflict_resolution`; preregister
   the canary success criteria.
3. Gated, reversible canary at `conflict_resolution` only; BCVF fallback live.
4. Defer `deliberative` (needs real obstacle wiring + a grasp-safety evaluator)
   and `task_allocation` (redundant filter) to later phases.
