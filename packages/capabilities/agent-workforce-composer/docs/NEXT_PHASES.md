# Next Phases

P1 answered *who is eligible*; P2 answered *who should be chosen*. Both have
landed, as has P2.1. The authority for what is and is not implemented is
`version_info()` in `src/ugence_agent_workforce_composer/version.py` — every
claim below is one of its booleans, not a plan restated as a fact.

## Delivered

**P1 — eligibility.** Canonical object model, compiler adapter, hard-constraint
eligibility, deterministic replay
(`canonical_object_model_implemented`, `compiler_adapter_implemented`,
`hard_constraint_eligibility_implemented`, `deterministic_replay_verified`).

**P2 — ranking and composition.** Deterministic agent ranking, multi-agent team
composition, permission bounding, fallback planning, and the immutable
`AgentTeamPlan` — offline, deterministic, explainable, side-effect-free
(`deterministic_ranking_implemented`, `agent_ranking_implemented`,
`team_composition_implemented`, `permission_bound_proposal_implemented`,
`fallback_planning_implemented`, `agent_team_plan_implemented`).

**P2.1 — compiler IR v2.** `workflow_ir` v1 and v2 support, the v2 adapter,
overlay reduction, v1 fingerprint compatibility, and the v1/v2 equivalence
harness (`compiler_workflow_ir_v1_supported`, `compiler_workflow_ir_v2_supported`,
`compiler_v2_adapter_implemented`, `overlay_reduction_implemented`,
`v1_fingerprint_compatibility_verified`, `v1_v2_equivalence_harness_implemented`).

P2.1's carried limitations are recorded in
[`KNOWN_LIMITATIONS_P2_1.md`](KNOWN_LIMITATIONS_P2_1.md) and are not repeated here.

## Not implemented

Each is `false` in `version_info()`:

- **Ugence Governance Studio — Eligibility and Composition Explorer**: a thin web
  console, deterministic demo API and private deployment consuming the real P1 +
  P2 APIs without reimplementing any logic; execution and authority stay strictly
  outside that boundary (`governance_studio_api_implemented`).
- **Permission assignment and granting** — P2 proposes bounds; it grants nothing
  (`permission_assignment_implemented`, `permission_granting_implemented`).
- **Agent Runtime handoff adapter** (`AgentTeamPlan` → runtime assignment;
  narrowing-only) and runtime execution (`runtime_handoff_implemented`,
  `runtime_execution_implemented`).
- **H16 runtime reconciliation / compatibility shims** (P4), gated by
  serialization + import-boundary tests. The Phase 0 "identity-preserving
  re-export" is not viable and the `COMPATIBILITY_FACADE_CANDIDATE` disposition is
  deferred — see [`H16_CANONICALIZATION_STATUS.md`](H16_CANONICALIZATION_STATUS.md)
  (`h16_migration_implemented`).
- **H22 multi-workflow scheduling integration** — schedules already-staffed
  workflows (`h22_integration_implemented`).
- **Model Selection interop** — AWC emits `model_requirement_ref`s and never ranks
  models (`model_selection_integration_implemented`).
- **Live registry ingestion and live availability**
  (`live_registry_implemented`, `live_availability_implemented`).
- **Pilot validation and production certification**
  (`pilot_validated`, `production_certified`).
