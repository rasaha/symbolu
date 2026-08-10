# ACP Phase 0 — Compatibility Report

Proof that ACP is additive and changes no current runtime behaviour.

---

## 1. No production call site imports ACP

```
$ grep -rl "autonomous_control_plane" symbolu_robotics --include=*.py \
    | grep -v "/autonomous_control_plane/"
NONE — clean
```

Only files *inside* the ACP package reference it. This is also asserted at test
time by `TestZeroRuntimeBehaviourChange::test_no_production_module_imports_acp`,
so a future accidental import fails CI.

## 2. Existing robotics test suite: byte-identical before/after

The existing suite has **pre-existing** issues unrelated to ACP (recorded here so
they are not misattributed): 4 modules fail collection (e.g.
`test_tiers.py` imports a non-existent `ReflexiveConfig`), and 6 formula tests
fail (BCVF/USE/SCC). ACP does not touch any of it.

| measurement | BEFORE adding ACP | AFTER adding ACP |
|---|---|---|
| `test_safety.py` + `test_formulas.py` | **98 passed, 6 failed** | **98 passed, 6 failed** |
| `symbolu_robotics/tests/` collection | **104 collected, 4 errors** | **104 collected, 4 errors** |

Identical. ACP adds no test to the existing `symbolu_robotics/tests/` directory
(its tests live under `autonomous_control_plane/tests/`), so the existing suite's
counts cannot move — and they did not.

## 3. Independently importable, no new hard dependency

- `import symbolu_robotics.autonomous_control_plane` succeeds standalone
  (`version 0.1.0-phase0`).
- The core is **standard-library only**: no `numpy`, `torch`, `rclpy`, or
  hardware driver is imported. Asserted by
  `TestZeroRuntimeBehaviourChange::test_acp_imports_no_numpy_or_ros`.
- `pytest` is used only to *run* tests; the suite also runs under
  `python -m unittest` with zero third-party dependencies.

## 4. Disabled by default

ACP is a library with no runtime wiring. Nothing constructs or calls it from the
robot control path; the BCVF call sites (`tiers/deliberative.py`,
`coordination/{conflict_resolution,task_allocation}.py`) are untouched and remain
the executable baseline and the rollback target.

## 5. ACP self-test result

`44 passed` (pytest and unittest). See `ACP_PHASE0_IMPLEMENTATION.md` §3.

## 6. Rollback

Because ACP is purely additive and unreferenced, rollback is deleting the
package directory; no production code depends on it.
