# Cloud Scaling Phase 5C — production ActionGate admission, scoped and ratified

**Status:** ratified 2026-09-04 by the repository owner. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1, cloud-scaling
ladder, after 5B-2). Grounded on `ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md` §7
("Phase 5C — ActionGate admission semantics; retry and state-change handling; the
`ActionAuthorization` shape; idempotent admission under the D-6 key"),
`ADR_RISK_AUTHORITY_PHASE5_ENVELOPE_ISSUANCE_RATIFICATION.md` (the envelope and its
artifact bindings) and `ADR_RISK_AUTHORITY_DURABLE_PERSISTENCE_SCOPING.md` (the
store posture). This record authorizes no code change; it fixes what the
implementation must do.

## The question

Can a `RiskAuthorizationEnvelope` issued through `EnvelopeIssuanceSeam` (Risk
Authority 0.7.0, composed by `cloud-scaling-envelope-issuance` 0.1.0) be admitted
to a `CanonicalAction` without lifting the reference ActionGate containment?
**Not today, and not because of containment alone.** The envelope's generic
`Scope` carries a purpose and nothing else, so the reference gate's tool check
would deny every capacity action even in reference mode. 5C must reconcile the
action against what the envelope *binds* — the five 5B-4 artifact digests — while
Risk Authority keeps envelope verification for itself and `authorize_action` stays
contained.

## What exists `[V]`

| Finding | Where |
|---|---|
| `authorize_action` raises `ProductionContainmentError` in production mode; in reference mode it builds a `CanonicalAction` from the request and calls `ReferenceActionGate` | `packages/risk_authority/src/risk_authority/api/dependencies.py:840-925` |
| `ActionGatePort.authorize` takes envelope, action, runtime identity, key ring, revocation state, `now`, satisfied conditions; the reference gate verifies the envelope (signature, window, tenant and session, revocation, epoch), binds identity, then checks purpose, tool allow and deny sets, data classes, destination, money amount and conditions | `integrations/actiongate.py:42-180` |
| The reference gate's own note F-D: `jurisdictions`, `max_autonomy_level` and per-resource constraints bound issuance but are not enforced at the gate | `integrations/actiongate.py:95-100` |
| A cloud-scaling decision's scope is `Scope(purposes=(cloud_scaling.capacity_action,))` and nothing else | `packages/integration/cloud-scaling-risk-integration/src/ugence_cloud_scaling_risk_integration/projection.py:369` |
| The evaluation seam creates the case with `model_id = request.subject_id`, so `envelope.model_id == envelope.subject` | `api/evaluation_seam.py:437-438` |
| `CanonicalAction` has no magnitude field; its only numeric bound is `amount_minor_units` (money) | `domain/actions.py:20-36` |
| `ActionAuthorization.expires_at` is typed `Optional[object]`; no repository port exists for authorizations; ids come from the process counter | `domain/actions.py:46-60`; `persistence/repositories.py`; `dependencies.py:884` |
| The 5B-4 envelope binds, by digest, the candidate, the policy-authenticity artifact, the producer-attestation artifact, the execution target scope and the D-6 idempotency key | `cloud-scaling-envelope-issuance/src/.../identifiers.py`, `verification.py` |
| The four canonical capacity action types are `no_change`, `scale_up`, `scale_down`, `coordinated` | `cloud-scaling-risk-integration/src/.../identifiers.py:60-61` |
| Downstream custody: `AuthorizationContext.authorization_ref` and `AuthorizedActionIdentity.authorized_action_fingerprint` enter Action Clearance; a `CLEAR` receipt admits `reserve_once` under `ExecutionKey(tenant, authorization_ref, fingerprint, target_ref, operation)`; `PRIOR_CONSUMPTION` dedupes at reservation on that key | `packages/capabilities/action-clearance/src/ugence_action_clearance/models/authorization.py:21-73`; `packages/integration/execution-reservation/src/ugence_execution_reservation/execution_key.py:34-72`, `reservation.py:258-300` |
| RA-8 correlates every effect on `(tenant_id, workflow_instance_id, envelope_id, authorized_action_digest, attempt_id)` | `packages/integration/risk-authority-execution-assurance/src/.../contracts.py:183-200` |
| `packages/providers/actiongate` is a Governance Provider Framework provider: it imports nothing from Risk Authority and maps every uncertainty to `INDETERMINATE` | its README and source |

## What admission needs `[I]`

An envelope loaded from the durable store and verified by the kernel; the
presented `ExecutionTargetScope` and candidate digest, so the action can be
reconciled against the envelope's bindings; a stable authorization identity so
Action Clearance, the execution ledger and RA-8 all correlate on one ref; and a
place to persist the authorization.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Home | **`ActionAdmissionSeam` in `risk_authority.api`**, beside `EnvelopeIssuanceSeam`, is the only production path from an envelope to an `ActionAuthorization`. `RiskAuthorityApplication.authorize_action` stays contained in production mode. A new integration package **`cloud-scaling-action-admission`** implements `ActionGatePort` for capacity actions and is the ladder's 5C composition root. |
| D-2 | Mapping | A **fixed `CanonicalAction` mapping**: `tenant_id` from the envelope; `actor_id = envelope.subject`; `model_id = envelope.model_id`; `action_type = target_scope.action_type`, one of the four canonical types; `target_id = target_scope.digest()`; `purpose = cloud_scaling.capacity_action`; `data_classes`, `destination`, `amount_minor_units` and `currency` empty. Magnitude is bounded by reconciling the presented `ExecutionTargetScope` against the envelope's `cloud-scaling.execution-target-scope` binding and by the 5B-0B verified bounds the candidate carries, **never** by the generic scope. **Widening the 4C `requested_scope` is rejected**: it moves the request digest, the candidate digest and the frozen fixtures across three packages for a bound the bindings already carry. |
| D-3 | Idempotent admission | **`authorization_id = auth.v1:sha256(tenant_id, envelope_id, action_digest)`**, derived, never allocated. A new **`AuthorizationRepository`** port (SQLite adapter under the 0.7.0 posture, in-memory reference refused in production) persists each authorization. Re-admitting the same pair returns the stored authorization with disposition **`REPLAYED`**; a different action digest under an existing id is refused. The D-6 key travels from the envelope binding into `AuthorizationContext`, so `ExecutionKey` is stable and the reservation ledger dedupes exactly once. |
| D-4 | Port posture | **Envelope verification is kernel-owned**: the seam reads its clock once, loads the envelope from the store, verifies signature, window, tenant and session binding, revocation and epoch, and refuses before any port runs. The injected `ActionGatePort` must declare `is_production_authoritative = True`; `ReferenceActionGate` and any subclass are refused. The port may return **`AUTHORIZED` or `DENIED` only**; any other value or an exception is `DENIED`. `packages/providers/actiongate` is a peer provider, not this port. |
| D-5 | Containment after admission | **An `ActionAuthorization` executes nothing.** 5X credentials and an execution-reservation are still required; `executable` remains a permanently-`False` property. `expires_at` is typed `datetime` and equals the envelope's; the RA-8 correlation tuple is minted from the authorization's `envelope_id` and `action_digest`. The seam emits `ACTION_AUTHORIZED` or `ACTION_DENIED` governance events as the reference path does. |

## Gaps that survive `[G]`

No `AuthorizationRepository` exists yet; the seam's `model_id == subject_id`
conflation is carried, not corrected; the F-D unenforced scope dimensions remain
unenforced for capacity actions (they have no meaning there); ACP and trajectory
hooks (`trajectory_version`) are untouched; 5X credentials and 5D execution are
unbuilt, so live infrastructure mutation stays structurally blocked.

## Next step

Implement `ActionAdmissionSeam`, the `AuthorizationRepository` port and its SQLite
adapter in Risk Authority (0.8.0), then build `cloud-scaling-action-admission`
against the seam with the D-2 mapping.
