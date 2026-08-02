# ACP Request / Result Contract Inventory

Exact live request and result surfaces across the three framings. There is **no single canonical
request/result contract**; each framing has its own shape.

## 1. Robotics core

- **Request:** implicit — `(CanonicalWorldState, Sequence[CanonicalActionCandidate], Mapping[candidate_id,
  Sequence[constraint]])` passed to a selector `.select(...)`. No `Request` type.
- **Result:** `SelectionOutcome{decision: ActionDecision, selected: Optional[CanonicalActionCandidate],
  trace: DecisionTrace}` (`action_selection.py:55`).
- **Authorization result:** `ControlAuthorization` (`authorization.py:34`) — the one-shot grant with
  `expiry_time_s` and `action_identity` binding.

| Field family | Present? | Evidence |
|---|---|---|
| Reason codes | Yes (plain `str`) | `ConstraintResult.reason_code`, `RejectedCandidate.reason_code` |
| Deterministic fingerprints | Yes | `CanonicalActionCandidate.identity`, `CanonicalWorldState.version`, `grant_id` (SHA-256) |
| Action fingerprint | Yes | `ControlAuthorization.action_identity` binds the exact candidate hash |
| Timestamps | Injected floats | `issued_time_s`, `expiry_time_s`, `observation_time_s`, `freshness_s` (no wall clock) |
| Expiry | Yes | `expiry_time_s`; checked `now_s > expiry_time_s` (`authorization.py:124`) |
| Idempotency / consumption | **No** | "one-shot" is documentation only; no nonce/consumption tracking |
| Authorization reference | Partial | `DecisionTrace.authorization_identity` exists but selectors leave it `None` |
| Tenant / correlation ID | Partial | `decision_id`, `mission_id`, `constraint_set_version`; no tenant field |
| Obligations | Partial | `permitted_constraints`, `EXECUTE_WITH_CONSTRAINTS` |
| Escalation | Yes | `SAFE_STOP`/`DEGRADE_MODE`/`REPLAN` + `FailureState` postures |
| Versioning / serialization | Content hashing | canonical JSON (`identity.py:96`), `to_dict()` on traces |

## 2. Cloud adapter (the consumed surface)

- **Request inputs:** `CloudWorldState`, `CloudActionCandidate`, an opaque `AuthorizationVerdict` token, plus
  `acp_recommendation`, `acp_validity`, `identity_bound`.
- **Result:** `CompositionResult` with `CombinedOutcome` (PROCEED / BLOCKED_BY_AUTHORIZATION /
  PENDING_AUTHORIZATION / HELD_BY_ACP) via `compose(...)`; ACP's own advisory is `CloudRecommendation`
  (PROCEED / PROCEED_WITH_CONSTRAINTS / REOBSERVE / HOLD).
- Consumers (`cer_v0_*`) rely on the enum **`.value` strings** and the `CloudWorldState`/`CloudActionCandidate`
  field schema — a de-facto serialization contract that is **not** versioned or snapshotted.

## 3. Console digital clearance (concept #3)

- **Request:** `OperationalSignals{error_budget_remaining, cluster_health, change_freeze_active}`.
- **Result:** `ClearanceVerdict{disposition: "CLEAR"|"HOLD", reason_codes: List[str], evaluated:
  Dict[str,str]}`.
- This is the *literal* "clearance request/result" the audit anticipated, but it is a **different, thinner**
  contract than the robotics one and shares no code.

## 4. Neutral seam (already stable & frozen)

`ActionGovernanceRequest` (`authorization_expired`, `idempotency_key`, `correlation_id`, `evidence_refs`,
`decision_refs`, `policy_refs`) → `ActionGovernanceResult` (`outcome ∈ {…, EXPIRED}`, `expiry`,
`obligations`, `constraints`, `reason_codes`, `fingerprint`). This is the contract a future ACP product
would most naturally consume/extend, and it is already serialization-frozen in `ugence_governance_contracts`.

## Equivalence to the anticipated `Clearance*` family

The audit anticipated `ClearanceRequest / ClearanceResult / ClearanceStatus / ClearanceReasonCode /
ClearancePolicy / CurrentStateSignal / AuthorizationReference / ActionFingerprint / ClearanceFingerprint`.
The repository uses different names and, critically, **three different shapes for the same discipline**.
`ActionFingerprint` is fully present; `AuthorizationReference`, `CurrentStateSignal`, and
`ClearanceFingerprint` are partial; `ClearanceStatus`/`ReasonCode`/`Policy`/`Request`/`Result` have no single
canonical type.

## Contract-stability finding

**There is no stable, single request/result contract for the ACP discipline.** This is a **PREREQUISITE**
(not a blocker in itself, but must be resolved before packaging): a governance ACP package needs one named
`Clearance*` (or reuse of the neutral `ActionGovernance*`) family that the robotics, cloud, DB, and console
adapters all speak — replacing today's three divergent shapes and the `.value`-string coupling.
