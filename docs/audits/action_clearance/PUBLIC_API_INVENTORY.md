# ACP Live Public-API Inventory

Derived from live code. Machine-readable companion: `acp_api_inventory.json`. The repository uses
**domain-specific envelope types, not a `ClearanceRequest/ClearanceResult` family**.

## Robotics core (`symbolu_robotics/autonomous_control_plane/`)

### Enums (verdict / status vocabulary)

- `ActionType` (`envelopes.py:24`): MOVE, STOP, HOLD, MANIPULATE, YIELD, CUSTOM.
- **`ActionDecision`** (`envelopes.py:33`) — the core verdict enum: `EXECUTE`,
  `EXECUTE_WITH_CONSTRAINTS`, `REPLAN`, `REQUEST_MORE_OBSERVATION`, `DEGRADE_MODE`, `SAFE_STOP`,
  `NO_SAFE_ACTION`.
- `ConstraintKind` (`constraints.py:21`): HARD, SOFT.
- `OperatingMode` (`world_state.py:25`): AUTONOMOUS, DEGRADED, MANUAL, MAINTENANCE.
- `FailureState` (`failure_state.py`): NOMINAL, DEGRADED, SAFE_HOLD, MRM, ESTOP, HANDOVER.
- Predictor states (`predictor_evidence.py`): ReliabilityState/VarianceState/DropoutState/CalibrationState.

### Data contracts (frozen dataclasses)

- `CanonicalWorldState` (`world_state.py:81`) — `.version` content identity.
- `CanonicalActionCandidate` (`envelopes.py:44`) — `.identity` content identity.
- `ConstraintResult` (`constraints.py:26`) — `constraint_id, kind, passed, observed_value, required_bound,
  comparator, reason_code, evidence_ref`; `.blocks_admissibility`.
- `SelectionOutcome` (`action_selection.py:55`) — `decision, selected, trace` (the result object).
- `DecisionTrace` (`decision_trace.py:40`) — full rationale incl. an (unpopulated) `authorization_identity`.
- `ControlAuthorization` (`authorization.py:34`) — `decision_id, action_identity, world_state_version,
  constraint_set_version, decision, issued_time_s, expiry_time_s, permitted_constraints`; `.grant_id`
  (content hash, **not** a cryptographic signature).

### Functions / classes

- `identity(value, *, domain, version=1)` (`identity.py:107`) — domain-separated SHA-256.
- `filter_admissible(candidates, candidate_constraints)` (`action_selection.py:62`) — non-compensatory hard
  filter.
- `DeterministicActionSelector.select(...)`, `LexicographicActionSelector.select(...)`.
- `ReferenceControlAuthorizer.authorize(...)`, `ReferenceCommitRevalidator.revalidate(...)`.

### Protocols (`interfaces.py`, all `@runtime_checkable`)

`WorldStateProvider, PredictorReliabilityEvaluator, HardConstraintEvaluator, SoftObjectiveEvaluator,
DeterministicActionSelector, ControlAuthorizer, CommitStateRevalidator, FailureStateMachine,
DecisionTraceSink`.

## Cloud adapter (`.../cloud/`) — the surface external consumers deep-import

- `CloudRecommendation` (`cloud/outcomes.py`): PROCEED, PROCEED_WITH_CONSTRAINTS, REOBSERVE, HOLD.
- `AuthorizationVerdict` (`cloud/composition.py`): DENY, REQUEST_MORE_EVIDENCE, SIMULATE_AND_RETRY,
  ESCALATE_TO_HUMAN, ALLOW_WITH_CONSTRAINTS, ALLOW — an **opaque mirror** of ActionGate's six outcomes.
- `CombinedOutcome` (`cloud/composition.py`): PROCEED, BLOCKED_BY_AUTHORIZATION, PENDING_AUTHORIZATION,
  HELD_BY_ACP.
- `compose(authorization, acp_recommendation) -> CompositionResult`.
- `CloudWorldState`, `CloudActionCandidate`, `CloudOperationalEvidence`, `CloudShadowAdapter`.

**Note:** the frozen top-level `autonomous_control_plane/__init__.py __all__` does **not** re-export `cloud`;
consumers reach it by deep import. The advertised "interface freeze" is not the surface consumers depend on.

## Console digital clearance (`ugence_console_api/`) — concept #3

- `OperationalSignals` (`models.py:107`): `error_budget_remaining, cluster_health, change_freeze_active`.
- `ClearanceVerdict` (`models.py:116`): `disposition` (CLEAR/HOLD), `reason_codes: List[str]`,
  `evaluated: Dict[str,str]`.
- `clear(signals) -> ClearanceVerdict` (`operational_safety.py:29`).

## Neutral seam (`packages/governance-contracts/`)

- `ActionGovernanceOutcome`: AUTHORIZED, AUTHORIZED_WITH_CONSTRAINTS, DENIED, INDETERMINATE, **EXPIRED**.
- `ActionGovernanceRequest.authorization_expired: bool = False`.
- `ActionGovernanceResult`: `outcome, constraints, obligations, expiry, authority_basis, reason_codes,
  provider_trace_id, fingerprint`.

## Anticipated vs actual type names

| Anticipated | Actual (or absent) |
|---|---|
| `ClearanceRequest` | absent — implicit tuple / `OperationalSignals` / `CloudWorldState`+`CloudActionCandidate` |
| `ClearanceResult` | absent — `SelectionOutcome` / `ClearanceVerdict` / `CompositionResult` |
| `ClearanceStatus` | absent — `ActionDecision` / `CloudRecommendation` / disposition string / `CombinedOutcome` |
| `ClearanceReasonCode` | absent — plain `str` tuples/lists (no enum) |
| `ClearancePolicy` | absent — `ThresholdConstraint` sets / `CloudConstraintConfig` / hard-coded thresholds |
| `CurrentStateSignal` | partial — `CanonicalWorldState` / `CloudWorldState` / `OperationalSignals` |
| `AuthorizationReference` | partial — `ControlAuthorization.action_identity`; `DecisionTrace.authorization_identity` unpopulated |
| `ActionFingerprint` | present — `CanonicalActionCandidate.identity`, `action_identity` binding |
| `ClearanceFingerprint` | partial — `grant_id`; `CompositionResult` identity |

The absence of a single, named, stable request/result/status/reason-code family across the three framings is
a primary contract-stability gap (see `REQUEST_RESULT_CONTRACTS.md`, `RISK_REGISTER.md`).
