# ACP Interface Contracts (Phase 0)

The frozen deterministic interfaces (`autonomous_control_plane/interfaces.py`).
Each is a `typing.Protocol` (structural — reference implementations need not
inherit). Every contract states inputs, outputs, determinism, boundedness,
failure behaviour, and safety-criticality.

---

| interface | inputs → outputs | determinism | bounded | failure behaviour | safety-critical |
|---|---|---|---|---|---|
| **WorldStateProvider** | raw world model → `CanonicalWorldState` | pure w.r.t. inputs + injected clock; no ambient time | O(sources), fixed cap | raise on invalid/stale; never return a partial snapshot | **YES** |
| **PredictorReliabilityEvaluator** | predictor streams → `tuple[PredictorEvidence]` | threshold state machine; no softmax/learned weights | O(M·H), fixed M,H | fail closed: insufficient evidence → SUSPECT/FAILED or empty (ABSTAIN), never fabricated TRUSTED | **YES** |
| **HardConstraintEvaluator** | candidate + world → `tuple[ConstraintResult]` (HARD) | pure predicates, fixed order | O(C), fixed C | malformed feature → violation; no results → not admissible | **YES** |
| **SoftObjectiveEvaluator** | admissible candidate + world → finite float | fixed weights, no randomness | O(1) | raise on non-finite cost | NO (cannot admit) |
| **DeterministicActionSelector** | candidates + per-candidate constraints + world → `SelectionOutcome` | total-order tie-break; unique winner | O(K log K) | empty admissible → `NO_SAFE_ACTION`; no evidence → `REQUEST_MORE_OBSERVATION` | **YES** |
| **ControlAuthorizer** | decision + candidate + world + constraint version → `Optional[ControlAuthorization]` | pure; binds exact identities + freshness bound | O(1) | executable decision w/o candidate → raise; non-executable → `None` | **YES** |
| **CommitStateRevalidator** | authorization + candidate + current world + constraint version + now → `None` | pure exact-identity compare | O(1) | `StaleAuthorizationError` on drift/expiry; `AuthorizationBindingError` on action mismatch | **YES** |
| **FailureStateMachine** | target posture + event/reason (+operator) → `TransitionRecord` | fixed legal-transition table | O(1) | `IllegalTransitionError` on illegal/ungated move | **YES** |
| **DecisionTraceSink** | `DecisionTrace` → `None` | append-only, order-preserving | O(1)/record | raise on non-trace; never silently drop | NO (but MANDATORY) |

## Cross-cutting invariants

1. **Non-compensatory admissibility.** Only `HardConstraintEvaluator` results
   gate admissibility. `SoftObjectiveEvaluator` and any advisory (BCVF) run only
   on already-admissible candidates and can never resurrect an inadmissible one.
2. **No probabilistic authorization.** `ActionDecision` is a closed enum; no
   scalar "allow score" exists. `ControlAuthorizer` mints a grant only for
   `EXECUTE` / `EXECUTE_WITH_CONSTRAINTS`.
3. **Evidence/state binding.** Every authorization binds exact
   `world_state_version` + `constraint_set_version` + `action_identity`;
   `CommitStateRevalidator` re-checks them at commit (TOCTOU).
4. **Fail closed.** Missing/empty evidence never authorizes. The reference
   `NoConfiguredConstraintsEvaluator` demonstrates this: no constraints → no
   admissibility → `NO_SAFE_ACTION`.
5. **Determinism.** No interface admits randomness on the decision path; time is
   injected, never ambient; tie-breaks are total orders.
6. **Boundedness.** Every method's cost is a fixed bound in `M, H, K, C` — the
   precondition for the WCET budgeting the architecture requires.

## Reference implementations shipped (Phase 0)

- `NoConfiguredConstraintsEvaluator` — fail-closed HardConstraintEvaluator.
- `DeterministicActionSelector` — refuses without admissibility evidence.
- `ReferenceControlAuthorizer` / `ReferenceCommitRevalidator` — exact-identity
  binding + revalidation.
- `InMemoryDecisionTraceSink` — immutable trace store.
- `FailureStateMachine` — legal-transition validation + manual-reset gating.

These exist to prove composition, not to be production drop-ins.
