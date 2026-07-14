# ACP Phase 0 — Implementation Report

**Scope:** additive package scaffolding + interface freeze. No production
call-site migration, no BCVF replacement, no runtime wiring, no VC-brief change.
**Package:** `symbolu_robotics/autonomous_control_plane/` (stdlib-only core).
**Result:** the current BCVF implementation remains the executable baseline; ACP
is additive, independently importable, and disabled by default.

---

## 1. What was built

| module | responsibility |
|---|---|
| `errors.py` | typed, loud error hierarchy (schema, non-finite, identity, transition, authorization, configuration) |
| `identity.py` | deterministic canonical serialization + domain-separated SHA-256 identity |
| `world_state.py` | `CanonicalWorldState` (+ `Pose`, `Velocity`, `FreshnessSummary`, `OperatingMode`); `version` = content identity |
| `predictor_evidence.py` | `PredictorEvidence` (deterministic signals + reliability state); `BCVFAdvisory` optional, off by default, no authority |
| `constraints.py` | `ConstraintResult` (HARD/SOFT); `NoConfiguredConstraintsEvaluator` (fail-closed reference) |
| `envelopes.py` | `CanonicalActionCandidate`; `ActionDecision` (closed outcome set); `ActionType` |
| `authorization.py` | `ControlAuthorization` (reference, non-crypto) + `ReferenceControlAuthorizer` + `ReferenceCommitRevalidator` |
| `action_selection.py` | `DeterministicActionSelector` (fail-closed, total tie-break) + `SoftObjective` |
| `decision_trace.py` | `DecisionTrace` (structured explanation) + `InMemoryDecisionTraceSink` |
| `failure_state.py` | `FailureState` enum + legal-transition table + `FailureStateMachine` (manual-reset gated) |
| `interfaces.py` | 9 `Protocol` contracts with documented determinism / boundedness / failure / safety-criticality |
| `__init__.py` | curated public API; stdlib-only; independently importable |
| `tests/test_acp_phase0.py` | 44 tests (unittest; also runs under pytest) |

## 2. Design decisions worth recording

- **Stdlib-only core.** Poses/velocities are lightweight float dataclasses, not
  numpy arrays; trajectories are carried by *reference* (`trajectory_ref`), not
  as heavy arrays in the envelope. Result: **no numpy / ROS / hardware
  dependency** in the ACP core (asserted by a test). Phase-1 adapters will bridge
  to the existing numpy types.
- **Immutability.** All envelopes are `frozen` dataclasses; mappings
  (`extensions`, `metadata`) are frozen to `MappingProxyType`; collections are
  tuples. Reassignment raises `FrozenInstanceError`; mapping mutation raises
  `TypeError`.
- **Identity as version.** `CanonicalWorldState.version` *is* its content hash;
  candidates carry `origin_state_version`; authorizations bind exact
  world/constraint versions. This is the substrate for commit-time revalidation.
- **Fail-closed everywhere.** A missing evaluator returns no constraints →
  candidates are "not proven admissible" → the selector returns `NO_SAFE_ACTION`
  (or `REQUEST_MORE_OBSERVATION` when there is no evidence at all). Absence of
  evidence is never read as authorization.
- **BCVF demoted to advisory data.** `BCVFAdvisory` is `None` by default, has
  `advisory=True` fixed, lives only inside `PredictorEvidence`, and is never read
  by admissibility or authorization code — proven by
  `test_advisory_cannot_override_failed_hard_constraint`.
- **Failure-state names** follow the approved `ACP_FAILURE_STATE_MACHINE.md`
  (NOMINAL/DEGRADED/SAFE_HOLD/MRM/ESTOP/HANDOVER); the Phase-0 task's suggested
  names are mapped in a code comment.

## 3. Test summary

`44 passed` under both `pytest` and `python -m unittest` (stdlib, no pytest
dependency required). Coverage maps 1:1 to the Phase-0 checklist — schema
validation, immutability, deterministic identity, non-finite rejection,
stale/modified/expired authorization rejection, fail-closed selection, illegal
failure transitions, manual-reset gating, deterministic tie-break, trace
completeness, BCVF-off-by-default, advisory-cannot-override, and zero
runtime-behaviour-change (grep + numpy-free assertions).

## 4. Files changed

**Added (all additive):**
`symbolu_robotics/autonomous_control_plane/{__init__,errors,identity,world_state,
predictor_evidence,constraints,envelopes,authorization,action_selection,
decision_trace,failure_state,interfaces}.py`,
`.../tests/{__init__,test_acp_phase0}.py`, and the five `acp/ACP_PHASE0_*` /
`ACP_INTERFACE_CONTRACTS` / `ACP_CANONICAL_IDENTITY` docs.

**Modified production code:** none. **Existing tests:** unchanged (see
`ACP_PHASE0_COMPATIBILITY_REPORT.md`).
