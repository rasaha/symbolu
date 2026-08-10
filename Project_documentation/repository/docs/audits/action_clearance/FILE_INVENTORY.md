# ACP File Inventory

Machine-readable companion: `acp_file_inventory.json`. Paths are repo-relative; the ACP discipline is
implemented under the *Autonomous Control Plane* name (see `TERMINOLOGY_AND_SCOPE.md`).

## 1. Primary core — `symbolu_robotics/autonomous_control_plane/` (26 `.py`, ~4,890 LOC)

**Reusable core (frozen, stdlib-only) — 10 modules**

| File | Role |
|---|---|
| `errors.py` | Exception hierarchy (`ACPError`, `StaleAuthorizationError`, `AuthorizationBindingError`, …) |
| `identity.py` | Deterministic canonicalization + domain-separated SHA-256 identity |
| `world_state.py` | `CanonicalWorldState`, `OperatingMode`, `FreshnessSummary` (robotics-shaped) |
| `constraints.py` | `ConstraintKind` (HARD/SOFT), `ConstraintResult`, fail-closed evaluator |
| `envelopes.py` | `ActionType`, `ActionDecision` (verdict enum), `CanonicalActionCandidate` |
| `authorization.py` | `ControlAuthorization` grant, `ReferenceControlAuthorizer`, `ReferenceCommitRevalidator` |
| `action_selection.py` | `SelectionOutcome`, `filter_admissible`, deterministic/lexicographic selectors |
| `decision_trace.py` | `DecisionTrace`, `RejectedCandidate`, in-memory trace sink |
| `failure_state.py` | `FailureState` posture machine (NOMINAL…ESTOP/HANDOVER) |
| `interfaces.py` | Structural `Protocol`s for every stage |

**Robotics domain layer (NOT core; not reused cross-domain)**

`predictor_evidence.py`, `physical_evidence.py`, `constraint_library.py`, `adapters.py`, `shadow.py`,
`safety_adapters/{candidate_bridge,live_planner_adapter,trajectory_adapter,shadow_planner_hook}.py`.

**Cloud domain adapter (built on the core; the surface external consumers deep-import)**

`cloud/{envelopes,outcomes,constraints,composition,adapter}.py` — `CloudWorldState`, `CloudRecommendation`,
`AuthorizationVerdict`, `CombinedOutcome`, `compose()`, `CloudShadowAdapter`.

**Tests:** `tests/test_acp_phase0.py … phase3.py`, `tests/test_acp_cloud.py` (112 tests).

## 2. ACP design docs — `acp/` (60 markdown) and `ACP/` (2 markdown)

`acp/` holds the Autonomous Control Plane V1/V2/V2.1/V2.2 architecture, boundary, contract, freeze,
phase-preregistration, and results docs. Notable: `ACP_ARCHITECTURE.md`, `ACP_V1_FREEZE.md`,
`ACP_ACTIONGATE_BOUNDARY.md`, `ACTIONGATE_ACP_COMPOSITION_SPEC.md`, `RESPONSIBILITY_MATRIX.md`,
`ACP_LIVE_PATH_AUDIT.md`, `ACP_CROSS_DOMAIN_REUSE_ANALYSIS.md`. Full one-line listing in the
`acp_file_inventory.json` and in the source `acp/` directory.

`ACP/` (capitalized) holds the **AI Control Plane** unified-console plan (concept #2):
`PHASE1_GOVERNED_LOOP_DTO_CONTRACT.md`, `UGENCE_UNIFIED_CONSOLE_PLAN.md`.

## 3. Console digital clearance (concept #3) — `ugence_console_api/`

| File | Role |
|---|---|
| `capabilities/operational_safety.py` | `clear(OperationalSignals) -> ClearanceVerdict`; CLEAR/HOLD gate over freeze / cluster health / error budget |
| `models.py` | `OperationalSignals`, `ClearanceVerdict`, governed-loop DTOs |
| `orchestrator.py` | Governed loop Gateway → Verify → Authorize → **Clear** → Record |
| `capabilities/registry.py` | Maturity labels; the Clear stage is `"Implemented (shadow-mode) · Internally Validated"` |

## 4. Domain reuse (concept #4) — `cer_v0_3/acp_db/`

`adapter.py`, `safety.py`, `envelopes.py` — DB-domain operational-safety adapter reusing frozen
`cloud.compose()`; adds its own HARD checks (`safety.py:36-93`) for freshness / freeze / migration /
state-binding / rollback (see `DUPLICATION_DISPOSITION.md`).

## 5. Shadow & benchmark harnesses — `robotics_reliability_bench/acp_*`

`acp_shadow`, `acp_shadow2`, `acp_shadow3`, `acp_control_plane`, `acp_k8s_integrated`, `acp_cloud` — read-only
shadow/benchmark consumers of the core. `acp_k8s_integrated` reproduces ActionGate-side hashing + drift
checks for offline determinism (bench-only duplication).

## 6. Neutral seam & governance chain

| File | Role |
|---|---|
| `packages/governance-contracts/.../contracts/action.py` | `ActionGovernanceOutcome.EXPIRED`, `authorization_expired`, `expiry` (frozen seam) |
| `packages/governance-provider-framework/.../reference/action.py` | Reference provider returns `EXPIRED` on `authorization_expired` |
| `packages/governance-provider-framework/.../adapters/action_to_control_plane.py` | Computes `authorization_expired = cer.expires_at < now` |
| `decision_governance/actions/control_plane.py` | `OfflineDeterministicControlPlane` → `AuthorizationOutcome.EXPIRED` (Decision Authority owned) |

## 7. UNRELATED to ACP (recorded to prevent conflation)

`execution_gate/`, `execution_gate_shadow/` (Model Selection), `control_plane/`, `control_plane_shadow/`
(AI-governance eval of Model Selection), `bounded_shadow_pilot/` (cyber ActionGate customer pilot),
`ai_control_plane_v3/` (docs).
