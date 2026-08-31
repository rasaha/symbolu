# ACP Phase 2 — Results & Verdicts

**Run:** deterministic physical-safety shadow benchmark over the frozen corpus
(15 physical/abstract scenarios + 2 authorization). Machine-readable:
`robotics_reliability_bench/results/acp_shadow2_results.json`. Preregistration:
`ACP_PHASE2_PREREGISTRATION.md` (committed `d11c80d`, before this run).
**Shadow-only. Current runtime authoritative. Zero production edits. No
real-sensor claim.**

---

## 1. Headline (reported per provenance — never one merged number)

| metric | INTEGRATION_TEST (5) | AUTHORED_DET (10) | overall (15) |
|---|---|---|---|
| real-physical-evidence coverage | 1.00 | 0.83 | 0.88 |
| physical detection recall | **1.00** | **1.00** | **1.00** |
| false-rejection rate | 0.00 | 0.00 | **0.00** |
| **ACP inadmissible-selection count** | 0 | 0 | **0** |
| current-runtime physically-inadmissible-selection rate | 0.80 | 0.60 | **0.67** |
| ACP NO_SAFE_ACTION rate | 0.80 | 0.50 | 0.60 |
| stale-evidence / missing-evidence rate | 0 / 0 | 0.08 / 0.08 | 0.06 / 0.06 |

Global (all provenance): **deterministic-rerun identity 100%**,
**current-runtime-behavior-change count 0**, latency ~sub-ms/scenario.
Authorization: **state-revalidation rejection 1.0**, **evidence-binding rejection
verified**, **modified-trajectory rejection verified**.

## 2. Abstract-vs-physical agreement (conflict-score reliability)

**Agreement rate 0.333 (1/3).** The legacy abstract `safety_score` disagrees with
real physical checks **bidirectionally**:

| candidate | abstract admits (≥0.5) | physical admits | agree |
|---|---|---|---|
| hi_abstract (score 0.9) | yes | **no** (velocity breach) | ✗ over-admit |
| lo_abstract (score 0.4) | no | **yes** (physically safe) | ✗ over-reject |
| agree_safe (score 0.9) | yes | yes | ✓ |

**Finding:** the abstract conflict `safety_score` is an unreliable proxy for real
physical safety — it both admits physically-unsafe actions and rejects
physically-safe ones. Real physical evidence adds genuine value over it.

## 3. Per-scenario outcomes (selected)

| scenario | provenance | ACP decision | current-runtime pick inadmissible? |
|---|---|---|---|
| safe_within_limits | INTEGRATION_TEST | EXECUTE | no |
| position/velocity/obstacle/human violation | INTEGRATION_TEST | NO_SAFE_ACTION | **yes** |
| acceleration_breach | AUTHORED | NO_SAFE_ACTION | **yes** |
| emergency_stop / recovery | AUTHORED | EXECUTE (safe) | no |
| all_candidates_unsafe | AUTHORED | NO_SAFE_ACTION | **yes** |
| missing / stale evidence | AUTHORED | NO_SAFE_ACTION (fail-closed) | **yes** |
| planner_constraint_disagreement | AUTHORED | EXECUTE (safe alt) | **yes** (planner pick unsafe) |
| abstract_safe_physically_unsafe | AUTHORED | NO_SAFE_ACTION | **yes** |
| abstract_unsafe_physically_safe | AUTHORED | EXECUTE (physical rescues) | no |

ACP detected every unsafe candidate (recall 1.0), never rejected a safe one
(false-rejection 0.0), never selected an inadmissible candidate (0), and
fail-closed on missing/stale/evaluator-failure. The current runtime (no physical
gate) would have picked a physically-inadmissible action in 2/3 of scenarios.

## 4. Safety invariants (all proven — §9)

`test_acp_phase2.py`: physically-inadmissible never selected; abstract score
cannot override a physical failure; missing/stale evidence never EXECUTE; evidence
for A cannot authorize B; state-change / modified-trajectory invalidate
authorization; no safe survivors → NO_SAFE_ACTION; evaluator exceptions fail
closed; deterministic reruns; core stays stdlib-only; shadow bench has zero
behavior change and no actuation. **67 ACP tests pass** (pytest + unittest);
robotics baseline unchanged.

## 5. Limitations (binding)

- **Real modules are manipulator joint-space validators** with generic
  uncalibrated defaults (±π, ±2 m). They evaluate a candidate expressed as a
  **joint trajectory**.
- **They do not attach to the three BCVF call sites' current candidates.**
  Deliberative emits a velocity stub (bridgeable via the AUTHORED
  `candidate_bridge`, not production); conflict emits abstract strategies with
  **no candidate trajectory**; task has no trajectory. So real physical evidence
  lands at the trajectory/manipulation level — **not at the conflict call site**.
- **UNAVAILABLE (not fabricated):** stopping distance / braking margin, dynamic
  stability, path curvature, map/lane, per-trajectory actuator effort — no
  deterministic per-candidate module exists.
- **No real-sensor / recorded / simulator data** for this domain; scenarios are
  INTEGRATION_TEST (real repository fixtures) + AUTHORED. `jerk` / `self-collision`
  checks are validator-labeled "simplified".
- Corpus is small (17); this is decision-grade shadow evidence, not certification.

## 6. Verdicts

### Physical-safety integration → **`PHYSICAL_CONSTRAINTS_SUPPORTED_WITH_LIMITATIONS`**
A real, deterministic, tested module (`TrajectoryValidator`) evaluates a
meaningful subset of physical constraints per candidate with real thresholds
(recall 1.0, false-rejection 0.0, fail-closed, 0 inadmissible selections). BUT
key classes are UNAVAILABLE and the supported candidate representation (joint
trajectory) is not present at the live BCVF call sites.

### Real-scenario shadow evidence → **`REAL_SCENARIO_SHADOW_LIMITED`**
Repository-native INTEGRATION_TEST scenarios exercise the real validator and pass
cleanly, but coverage is narrow and there is **no recorded or real-sensor data**
(and the only simulator is off-domain). Sufficient to validate the integration
mechanism; not sufficient to claim broad real-world coverage.

### Canary readiness → **`SHADOW_CONTINUE`**
`READY_FOR_CONFLICT_CANARY` requires **adequate physical-evidence coverage at
conflict resolution** — and Phase 2 shows that condition is **NOT met**: conflict
candidates are abstract strategies with no candidate trajectory, so the real
physical validator cannot evaluate them, and the abstract `safety_score` there is
an unreliable proxy (agreement 0.333). Phase 1 tentatively favored a conflict
canary on the abstract score; **Phase 2's physical evidence retracts that** — a
conflict canary on abstract-only evidence is not justified. Other canary gates
(0 inadmissible selections, 100% rerun identity, 0 behavior changes,
binding/stale verified, bounded latency) are met, but the coverage gate is not.
No full migration recommended (Phase 1/2 rule).

## 7. Rollback & kill-switch plan

Because Phase 2 is purely additive and unreferenced by production:
- **Rollback:** delete `symbolu_robotics/autonomous_control_plane/safety_adapters/`
  and `robotics_reliability_bench/acp_shadow2/`; no production code depends on
  them. The ACP core (stdlib) and BCVF call sites are untouched — the current
  runtime is the standing baseline.
- **Kill switch (for a future gated canary, not enabled now):** any canary must
  ship behind a default-OFF, reversible flag with (a) BCVF retained as the live
  fallback, (b) a supervisor that reverts to the BCVF decision if ACP raises,
  times out, or returns `EVALUATOR_FAILED`, and (c) an operator-triggered global
  disable. None of this is wired in Phase 2 — ACP performs no actuation.

## 8. Recommended next step (Phase 3)

Wire a production candidate→trajectory path for the call site that most needs
physical evidence (deliberative manipulation, where trajectories are natural), so
the real validator attaches to a live call site; gather repository-native /
simulator scenario families with broader coverage; then re-evaluate canary
readiness with physical evidence actually present at a call site. The conflict
canary should be reconsidered only if conflict maneuvers are given real
candidate trajectories — the abstract score alone is not a safe gate.
