# Cloud Scaling Phase 5D — bounded execution, scoped and ratified

**Status:** ratified 2026-09-04 by the repository owner. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1, cloud-scaling
ladder, after 5X). Grounded on `ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md` §7
("Phase 5D — provider adapters; dry-run versus LIVE gating; bounded blast radius;
rollback; the execution-request and execution-record shapes") and §2 ("Live
execution is structurally blocked until 5X"), and on
`ADR_CLOUD_SCALING_PHASE5X_CREDENTIAL_BROKER_SCOPING.md` (the grant this phase
consumes). This record authorizes no code change; it fixes what the
implementation must do.

## The question

Can a `CredentialGrant` for a `RESERVED` reservation be consumed to dispatch
exactly one bounded capacity change today? **No.** Cloud Scaling Operations has a
bounded executor with real gates, but it authorizes on its own
`ExecutionAuthorization`, "minted by an external governance authority" that
nothing in the ladder mints; verifies it with an in-process HMAC secret; keeps
float epoch time; and knows nothing of grants, reservations, envelopes or RA-8.
5D is the adapter that makes the ladder's artifacts the only way into that
executor, and LIVE stays blocked until every precondition is proven, not
configured.

## What exists `[V]`

| Finding | Where |
|---|---|
| Four modes: `DRY_RUN` proposes with no authority, `SHADOW` reads only, `SIMULATION` and `LIVE` apply and fail closed without authority. The default mode is `DRY_RUN`; live is off by default | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/contracts.py:20-27`; `README.md:12-16,34-39` |
| `execute` runs, in order: the mode gate; `verify_authorization` (window, issuer, signature, tenant, action, target, recommendation, replica bounds, delta, cluster, namespace and resource allowlists); idempotency replay by request digest and authorization id, with a reused key for a different request raising `ExecutionIntegrityError`; the LIVE preconditions (injected backend, audit sink, no insecure TLS, readiness); apply; idempotency completion. Backend errors and concurrency conflicts emit `FAILED`, never `APPLIED` | `executors.py:192-330`; `authority.py:60-140` |
| `ExecutionAuthorization` is an operations-local shape with float `issued_at` and `expires_at`, an HMAC signature, and an `issuer` verified against `issuer_secrets` that `ReferenceAuthorityVerifier` holds in process | `contracts.py:61-108`; `authority.py:36-58` |
| The Kubernetes backend takes an injected client, refuses without one and loads no credential at import; the audit sink bans tokens, credentials, private keys and secret-bearing headers | `k8s_executor.py:28-47`; `audit.py:4` |
| `ExecutionReceipt` carries outcome, mode, target, pre and post state, `applied`, `authorization_id`, `recommendation_id`, `idempotency_key`, a float timestamp and a receipt hash — and no envelope id, grant id, reservation id or action digest | `contracts.py:143-200` |
| `RollbackCoordinator` re-enters the executor with a `RollbackAuthorization` that is either a full authorization or a bare `RollbackPolicy` | `rollback_coordinator.py:24-110` |
| `ProductionOrchestrator` runs a controller-to-execution loop with an auto-approve threshold, guarded by the note that an auto-approved recommendation cannot authorize its own mutation; the CLI accepts an authorization file with `--mode live --confirm` | `orchestrator.py:151-300`; `README.md:73-74` |
| No module in operations names Risk Authority, an envelope, a grant or a reservation; the package reads `time.time` | grep over `src/`; `contracts.py:12,102-106` |
| Reservation lifecycle: `mark_dispatched` requires `RESERVED`, an unlapsed lease and a deadline after `as_of`; `record_observation` maps `SUCCEEDED` and `DUPLICATE` to `OBSERVED_SUCCESS`, `FAILED` and `REJECTED` to `OBSERVED_FAILURE`, anything else to `OUTCOME_UNCERTAIN`; transitions are forward-only by rank; reconciliation follows observation | `packages/integration/execution-reservation/src/ugence_execution_reservation/reservation.py:86-100,322-342`; `memory.py:261-354` |
| RA-8 correlates every effect on `(tenant_id, workflow_instance_id, envelope_id, authorized_action_digest, attempt_id)` and ingests an `EffectObservation` carrying `external_request_id`, `business_outcome` and `finality`; it introduces no execution ledger and owns no authority | `packages/integration/risk-authority-execution-assurance/src/.../contracts.py:181-272`; `README.md` |
| The neutral shapes: `ExecutionDispatchRequest(action_type, parameters, idempotency_key, correlation_id)`, `ExecutionDispatchResult`, `ExecutionObservation` | `packages/governance-contracts/src/ugence_governance_contracts/contracts/execution.py:27-80` |
| 5D may support dry-run before 5X; production LIVE stays blocked until 5X supplies credentials; a long-lived or broadly scoped credential in an executor is the failure mode 5X exists to prevent | `docs/architecture/ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md:28-39,228` |
| 5X now exists: a `CredentialGrant` carries a handle reference, the request digest, the role, the `Validity` window and the broker identity, and re-derives from the authorization, the reservation and the target scope through the 5X minter | `packages/integration/cloud-scaling-credential-broker/src/.../grant.py`, `request.py` |

## What dispatch needs `[I]`

One artifact the executor accepts that can only be derived from a grant, a
reservation and the authorized action; a mode gate that reads the grant's
validity and provenance, not the config's mode alone; a receipt that carries what
RA-8 correlates on; the reservation advanced at dispatch and at observation by
the same actor; rollback as a second bounded action, never a bare policy.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Home and entry | A new integration package **`cloud-scaling-bounded-execution`** with a **`BoundedExecutionSeam`** that is the **only** path from a `CredentialGrant` to `ControlledScalingExecutor.execute`. The seam mints the operations-local `ExecutionAuthorization` itself from the grant, the reservation and the target scope, with the seam as `issuer` and a verifier the seam injects, so the executor's existing gates run unchanged against ladder-derived values. The orchestrator's auto-approve path and the CLI's authorization file are **documented as reference entries** and are not production paths. |
| D-2 | What a dispatch binds | A **`BoundedDispatch`** request carries `grant_id`, `reservation_id`, `execution_key`, `target_scope_digest`, `envelope_id`, `authorized_action_digest` and the grant's `request_digest`. Before any client is touched the seam proves, at its **one clock read**: the grant exists in the grant store, is valid at the instant, and its request digest re-derives from the presented reservation, authorization and target scope through the 5X minter; the reservation is `RESERVED` with an unlapsed lease in the ledger; the target scope re-derives the authorized action digest. **The execution key's serialized form is the executor's `idempotency_key`**, so the executor's replay check and the ledger agree on one identity. |
| D-3 | LIVE gating | LIVE requires **all** of: a production-mode Risk Authority application; a production-mode execution ledger; a production-authoritative grant store and broker; a grant whose `handle_ref` does not carry the reference prefix; an injected backend built by the deployment from the grant handle **outside this repository**; and `require_readiness`. **Any absence resolves the effective mode to `DRY_RUN`, never to `SIMULATION`.** Dry-run and simulation require the same D-2 bindings but not a materialized grant. |
| D-4 | Blast radius and rollback | The executor's `TargetPolicy` ceilings (`max_replicas`, `max_replica_delta`) are set from the grant's role (`max_magnitude`, `max_delta`) and its allowlists from the role's resource, **never wider than the deployment's config**. **Exactly one `set_replicas` per dispatch.** Rollback is a **second bounded action** to the receipt's `pre_state` requiring its own admission, reservation and grant; a `RollbackAuthorization` carrying a bare policy is refused by the seam. |
| D-5 | The record | A **`BoundedExecutionRecord`** is minted from the receipt with the D-2 bindings, **aware instants**, `attempt_id` equal to the dispatch request id, `external_request_id`, and the executor's outcome mapped to `ExecutionBusinessOutcome`. The seam calls **`mark_dispatched` before apply and `record_observation` after**, and emits an **`EffectObservation`** for RA-8 from the same record. **Reconciliation stays RA-8's.** |

## Gaps that survive `[G]`

Operations' float clock and HMAC verifier are carried, not replaced; no
production backend factory from a grant handle exists in this repository; Phase
6 effect verification; the orchestrator loop remains a parallel path and needs a
containment ruling of its own.

## Next step

Implement `cloud-scaling-bounded-execution` against Cloud Scaling Operations
0.1.2, `cloud-scaling-credential-broker` 0.1.0 and `execution-reservation`
0.1.0 under D-1 … D-5, with the acceptance test dispatching one bounded change
in `SIMULATION` from a grant, advancing the reservation to `OBSERVED_SUCCESS`,
emitting an `EffectObservation`, and proving that every missing LIVE
precondition resolves to `DRY_RUN`.
