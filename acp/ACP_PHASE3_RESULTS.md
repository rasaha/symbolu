# ACP Phase 3 — Results & Verdicts

**Run:** deterministic live-path physical-safety shadow benchmark (17 scenarios +
2 commit-revalidation). Machine-readable:
`robotics_reliability_bench/results/acp_shadow3_results.json`. Preregistration:
`ACP_PHASE3_PREREGISTRATION.md` (committed `fe671bb`, before this run).
**Shadow-only. Authoritative runtime unchanged. Zero production edits. No
real-sensor claim.** Frequencies are reported only within this corpus; the
Phase-2 "67%" is not reused as a headline.

---

## 1. Headline (provenance-stratified)

| metric | LIVE (3) | RECORDED (2) | AUTHORED (12) | overall (17) |
|---|---|---|---|---|
| live-path adapter coverage | 0.67 | 1.00 | 0.67 | 0.71 |
| physical-evidence coverage (VALID) | 0.67 | 1.00 | 0.50 | 0.59 |
| missing/unsupported rate | 0.33 | 0.00 | 0.33 | 0.29 |
| **ACP-vs-validator agreement** (VALID) | **1.00** | **1.00** | **1.00** | **1.00** |
| authored detection recall | — | — | **1.00** | 1.00 |
| authored false-rejection | — | — | **0.00** | 0.00 |
| **ACP inadmissible-selection count** | 0 | 0 | 0 | **0** |
| current-runtime physically-inadmissible count | 0 | 1 | 5 | **6** |

Global: **rerun identity 100%**, **authoritative behavior-change count 0**, **hook
OFF⇒ON plan byte-identical**, **shadow error rate 0**, **sink dropped 0** (bounded
`deque`, maxlen 10000), latency **mean ≈ 1.1 ms / p95 ≈ 2.3 ms / max ≈ 2.7 ms**,
memory growth ≈ 1.26 MB (transient numpy/validator allocations, not the bounded
sink). Commit-time revalidation: **state-change rejected**, **modified-trajectory
rejected**.

## 2. Per-scenario (selected)

| scenario | provenance | live status | is_safe | ACP decision |
|---|---|---|---|---|
| live_move_nominal | LIVE | SUPPORTED | true | EXECUTE |
| live_wait_hold | LIVE | SUPPORTED | true | EXECUTE |
| live_grasp_unsupported | LIVE | UNSUPPORTED_COMMAND | — | NO_SAFE_ACTION (fail-closed) |
| recorded_mpc_clear | RECORDED | RECORDED_TRAJECTORY | true | EXECUTE |
| recorded_mpc_obstacle | RECORDED | RECORDED_TRAJECTORY | **false** | NO_SAFE_ACTION |
| authored_velocity_breach | AUTHORED (live path) | SUPPORTED | **false** | NO_SAFE_ACTION |
| authored_emergency_stop | AUTHORED (live path) | SUPPORTED | true | EXECUTE |
| authored_{malformed,nonfinite,missing,gripper} | AUTHORED | fail-closed status | — | NO_SAFE_ACTION |
| authored_{position,accel,obstacle,all_invalid} | AUTHORED | DIRECT | **false** | NO_SAFE_ACTION |
| authored_stale_state | AUTHORED | STALE | — | NO_SAFE_ACTION |
| authored_evaluator_exception | AUTHORED | EVALUATOR_FAILED | — | NO_SAFE_ACTION |

All 8 fail-closed statuses (unsupported / missing / dimension / nonfinite / stale
/ evaluator-failed, plus identity-mismatch in tests) are exercised and all yield
`NO_SAFE_ACTION`. ACP admits every genuinely-safe trajectory (move, wait,
emergency stop, mpc-clear) and rejects every unsafe one — agreement with the real
validator is 1.00.

## 3. Safety invariants (all proven — §10)

`test_acp_phase3.py` (17 tests): ACP never admits a validator-failed trajectory;
missing/stale/malformed/nonfinite/unsupported evidence never EXECUTE; commit
state-change + modified-trajectory invalidate the prior evaluation; candidate-A
evidence cannot validate candidate-B (identity mismatch); all-invalid →
NO_SAFE_ACTION; evaluator exceptions fail closed; deterministic reruns; hook OFF
returns None + no record; hook OFF⇒ON plan byte-identical; hook exceptions
contained (plan still returns); instrumented planner delegates + propagates
planner exceptions unchanged; bounded sink caps length + counts drops; records
`shadow_only`, no actuation. **84 ACP tests pass** overall (pytest + unittest);
robotics baseline unchanged.

## 4. Limitations (binding)

- **The live planner emits stub trajectories.** `TaskPlanner._plan_move` is a
  documented stub (fixed `[0.5,0,…]` velocity), so the live path only produces
  *safe* move/stop trajectories or an unsupported gripper command — it cannot
  emit a violating trajectory. Violation coverage therefore comes from
  `RECORDED` (real MPC) and `AUTHORED`. The integration mechanism is proven on a
  real path; the planner's trajectory realism is low.
- **No validated latency budget** exists for `TaskPlanner.plan` in the repo — a
  **missing production requirement**. Measured shadow latency (~1 ms) is well
  under the R3 tier's soft `<100 ms` reference, but that reference is not a
  validated budget.
- **Repository-native scenario coverage is thin** (5 real-planner scenarios;
  MPC is the only rich trajectory source and it already validates + is
  non-deterministic). No recorded or real-sensor data.
- Corpus is small (17); decision-grade shadow evidence, not certification.

## 5. Verdicts

### Live integration → **`LIVE_TRAJECTORY_INTEGRATION_LIMITED`**
A genuine current planner path (deliberative `TaskPlanner.plan`) is wired
end-to-end: real plan → production-shaped adapter → real `TrajectoryValidator` →
ACP decision, byte-identical output, fail-closed on all §2 conditions,
deterministic, ACP-vs-validator agreement 1.00. But the planner emits **stub
trajectories** (it cannot exercise a violation live), so realistic trajectory
diversity comes only from recorded/authored — the mechanism is supported, the
live trajectory realism is not. Hence *LIMITED*, not *SUPPORTED*.

### Operational shadow readiness → **`SHADOW_OPERATION_SUPPORTED`**
The hook is default-OFF, returns the authoritative plan byte-identically,
contains all its exceptions, writes to a bounded ring buffer (no DoS; 0 drops),
is deterministic (100% rerun identity), performs commit-time revalidation, and
never actuates. Latency is bounded (~1 ms). The one caveat — no repository latency
budget to bound against — is a missing production requirement, not a hook defect.

### Canary readiness → **`SHADOW_CONTINUE`**
Most §11 gates are met (genuine planner path; 0 ACP physical violations; 100%
determinism; 0 behavior changes; bounded storage; missing/stale fail-closed;
state/action binding verified; rollback+kill-switch tested; no high-severity
defect). Two gates are **not** met: **adequate repository-native/simulator
coverage** (thin; 5 real-planner scenarios, low diversity), and **bounded
latency** cannot be certified against a budget that **does not exist**. Combined
with the stub-planner limitation (a manipulation canary here would gate a
trivially-safe planner), the honest call is `SHADOW_CONTINUE`. No full migration
recommended.

## 6. Rollback & kill-switch procedure

- **Kill switch:** the hook is `enabled=False` by default; flipping it off (or
  never constructing `InstrumentedTaskPlanner`) disables all shadow work
  instantly. It is not wired into the tier loop in Phase 3, so it is already OFF
  in production.
- **Rollback:** delete `symbolu_robotics/autonomous_control_plane/safety_adapters/`
  and `robotics_reliability_bench/acp_shadow3/`; nothing in production imports
  them. The ACP core (stdlib) and all BCVF call sites are untouched — the current
  runtime is the standing baseline.
- **Tested:** hook OFF ⇒ byte-identical plan + no record (bench + tests); hook
  exception contained (test); bounded sink (test).

## 7. Phase 4 recommendation

Before a manipulation canary is justified: (1) integrate a **real, non-stub**
manipulation trajectory source at the live call site (e.g. wire the deterministic
parts of the MPC/trajectory path, or a real IK-based motion primitive) so the
live path can emit varied trajectories including near-violations; (2) **define a
cycle-time budget** for the deliberative/manipulation loop (the missing
production requirement) and validate shadow latency against it; (3) broaden
repository-native / simulator scenario coverage. Then re-run the shadow evaluation
and re-evaluate canary readiness. The current deliberative stub is too simple for
a canary to add value.
