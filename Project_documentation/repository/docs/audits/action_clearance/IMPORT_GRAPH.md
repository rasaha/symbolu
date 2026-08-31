# ACP Import / Dependency Graph (before migration)

## Text graph

```text
symbolu_robotics.autonomous_control_plane            (CORE — concept #1, robotics ACP)
  core (stdlib only): errors <- identity <- world_state/envelopes/constraints/predictor_evidence
                      <- authorization/action_selection/decision_trace/interfaces
                      <- constraint_library/adapters/shadow <- physical_evidence
  .safety_adapters.*  -> numpy + symbolu_robotics.safety.trajectory_validator (real, on-demand)
  .cloud.*            -> cloud_controller.action.{readiness,policy}, cloud_controller.recommend.safety
                         (real, lazy import; "do not touch the Kubernetes client")
      |
      |  (deep imports of .cloud.* and .safety_adapters.*)
      v
  <- cer_v0_1  (control_plane, spec, conformance/runner, _paths)              [PRODUCT]
  <- cer_v0_2  (control_plane, conformance/runner, profiles/*)               [PRODUCT]
  <- cer_v0_3  (control_plane, conformance/cross_domain,
                acp_db/adapter, acp_db/safety   = concept #4 "ACP DB")       [PRODUCT, shadow-only]
  <- robotics_reliability_bench/acp_{shadow,shadow2,shadow3,cloud,
                k8s_integrated,control_plane}                                 [SHADOW / BENCH]
  <- cer_v0_{1,2,3}/tests, acp_control_plane/test, acp_k8s_integrated/test    [TEST]
     (storygraph tests/compatibility/test_dependencies.py = asserts NO edge)

ugence_console_api                                   (concept #3 — DIGITAL clearance)
  models.ClearanceVerdict / OperationalSignals
  capabilities.operational_safety.clear  <- orchestrator.py (Clear stage), app.py (/v1/actions/clear)
  (NO import of symbolu_robotics.autonomous_control_plane — name reused as a label only)

governance chain clearance seam                      (owned by Decision Authority + GPF)
  ugence_governance_contracts.contracts.action (ActionGovernanceOutcome.EXPIRED, authorization_expired)
    <- packages/governance-provider-framework/.../reference/action.py (EXPIRED)
    <- packages/governance-provider-framework/.../adapters/action_to_control_plane.py (authorization_expired)
    <- decision_governance/actions/control_plane.py (AuthorizationOutcome.EXPIRED)

ACP/ (concept #2, AI Control Plane) + ai_control_plane_v3/   =  DOCS ONLY (no importable module)
```

## Dependency-direction facts

- **Core imports nothing from production.** The 10 frozen core modules use only the Python standard library
  (verified by `test_acp_phase0.py:374`, `test_acp_phase1.py:104`). No import of `governance-contracts`,
  `control_plane`, `actiongate`, ROS, or numpy in the core.
- **Production does not import the core** (grep-asserted governance test
  `test_no_production_module_imports_acp`). Only `cer_v0_*`, the benches, and tests import it.
- **Adapters depend downward on real deterministic modules** (`safety_adapters` → trajectory validator;
  `cloud` → `cloud_controller`) but only as read-only evaluators, loaded on demand — never in the core
  `__init__` graph.
- **No dependency inversion** in the robotics core: it is a dependency-clean leaf. The one structural
  concern is not inversion but **surface**: consumers depend on the *unfrozen* `.cloud.*` surface rather
  than a curated public API.

## After-migration note

A before/after import graph pair (as produced for the Model-Selection and GPF migrations) is **not** created
in this audit because migration is **not recommended**. If the project later proceeds, the after-graph must
show consumers importing a curated `ugence_action_clearance` public surface (not deep `.cloud.*`), with a
legacy re-export shim preserving object identity for `cer_v0_*` (see `COMPATIBILITY_STRATEGY.md`).
