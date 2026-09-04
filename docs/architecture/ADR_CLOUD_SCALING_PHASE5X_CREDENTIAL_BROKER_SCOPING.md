# Cloud Scaling Phase 5X — credential brokering, scoped and ratified

**Status:** ratified 2026-09-04 by the repository owner. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1, cloud-scaling
ladder, after 5C; D-1 there rules the Credential Broker is built as cloud-scaling
Phase 5X, not as a general package, and generalises only after 5D). Grounded on
`ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md` §7 ("Phase 5X — credential lifetime
and scope; least-privilege role derivation from `ExecutionTargetScope`; broker
trust model; credential binding to an admitted action") and on
`ADR_CLOUD_SCALING_PHASE5C_ACTION_ADMISSION_SCOPING.md` (the authorization this
phase consumes). This record authorizes no code change; it fixes what the
implementation must do.

## The question

What does an admitted, reserved capacity action exchange for a credential, and
what must this repository never hold to do it? **A broker port that receives a
package-minted, digest-bound credential request and returns an opaque,
short-lived handle whose scope is derived from the target scope and whose
lifetime is capped by the authorization, the reservation lease and the
envelope.** The repository holds no provider secret because the port is the
seam, exactly as the Trusted Evidence Authority signer port is a seam for key
custody.

## What exists `[V]`

| Finding | Where |
|---|---|
| 5X is deferred with four named questions: credential lifetime and scope, least-privilege role derivation from `ExecutionTargetScope`, broker trust model, binding to an admitted action. Production LIVE execution is structurally blocked until it exists; a long-lived or broadly scoped credential in an executor is the failure mode 5X prevents | `docs/architecture/ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md:27,35-38,225-226` |
| Phase 5A's README restates the boundary: 5X is short-lived Credential Broker materialization, not implemented; live execution may not precede it | `packages/integration/cloud-scaling-authorization-contracts/README.md:219-234` |
| `ExecutionTargetScope` carries tenant, account, action type, the four magnitudes, and optional compute group, resource class, environment, region, zone and namespace; its digest is bound into the envelope (5B-4) and is the action's `target_id` (5C D-2) | `authorization-contracts/src/.../target.py:117-150`; `cloud-scaling-action-admission/src/.../mapping.py` |
| An `ActionAuthorization` carries a derived `auth.v1:` id, the action digest, `expires_at` equal to the envelope's, a `disposition`, and a permanently-`False` `executable` | `packages/risk_authority/src/risk_authority/domain/actions.py:46-80` |
| `ExecutionKey(tenant_id, authorization_ref, authorized_action_fingerprint, target_ref, operation)`; `reserve_once` admits only a `CLEAR`, unexpired, unrevoked receipt naming the same key; a reservation carries a `lease` `Validity` and moves `RESERVED → DISPATCHED` through `mark_dispatched(reservation_id, dispatch_request_id, dispatch_deadline, as_of)` | `packages/integration/execution-reservation/src/ugence_execution_reservation/execution_key.py:34-72`, `reservation.py:56-67,126-150,258-300,350-352` |
| `Validity` is half-open, aware-only, refuses an inverted window and a `stale_after` outside it | `packages/governance-contracts/src/ugence_governance_contracts/contracts/validity.py:123-200` |
| The TEV pattern to mirror: `ReceiptSignerPort` declares `signer_authority_id`, `signing_key_id`, `signature_profile` and one method; `ReceiptSigningInput` is constructible only with a private token the curated API does not export; `os`, `sys`, `secrets`, `time`, `random`, `locale`, `platform` are banned package-wide by a structural test | `packages/trusted-evidence-authority/src/ugence_trusted_evidence_authority/authority/signing.py:120-188`; `tests/packaging/test_no_clock_or_environment.py:36` |
| Cloud Scaling Operations never loads a credential: the Kubernetes backend takes an injected client and refuses without one; the audit sink bans tokens, credentials, private keys and secret-bearing headers | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/k8s_executor.py:1-47`, `audit.py:4` |
| No credential concept exists in any package source; `ExecutionDispatchRequest` has no field for one | grep over `packages/` (non-test source); `governance-contracts/src/.../contracts/execution.py:27-31` |

## What brokering needs `[I]`

A request the broker cannot be handed by a caller: the authorization ref, the
execution key, the target-scope digest and the reservation id, minted by the
package from those artifacts after revalidating each. A role bounded by the
target scope, never by the caller. A lifetime that cannot outlive any of the
three windows it depends on. A handle the executor can present without the
repository ever seeing the secret.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Home and shape | A new integration package **`cloud-scaling-credential-broker`** with a **`CredentialBrokerPort`** Protocol mirroring the Trusted Evidence Authority signer port: `broker_authority_id`, `credential_profile`, `is_production_authoritative`, and `materialize(request) -> CredentialGrant`. A **`ReferenceCredentialBroker`** returns an inert handle and is refused by the production composition. `os`, `sys`, `secrets`, `socket`, `time`, `subprocess`, `urllib`, `http` and every cloud SDK and Kubernetes client are banned structurally over the AST and the dependency manifest. |
| D-2 | What a request binds | **`CredentialRequest` is package-minted behind a private token** the curated API does not export. It is minted only from an `ActionAuthorization` whose decision is `AUTHORIZED`, a reservation in state `RESERVED` whose `ExecutionKey.authorization_ref` names that authorization, and a presented `ExecutionTargetScope` whose digest equals the action's `target_id`. It carries `authorization_ref`, `execution_key`, `target_scope_digest`, `reservation_id` and a `request_digest` over all of them. The broker signs nothing; the grant carries the request digest so 5D can refuse a grant minted for another action. |
| D-3 | Role derivation | **Least privilege is a pure function of the target scope.** One operation from `action_type`; **`no_change` derives no credential at all**; one resource from account, compute group, resource class, namespace and region; the magnitude ceiling as the only parameter. The derived role statement is canonical and digested into the request. **The broker may narrow the role and never widen it**, checked on the returned grant. |
| D-4 | Lifetime | **`expires_at = min(authorization.expires_at, reservation.lease.expires_at, envelope.expires_at, issued_at + ttl_cap)`**, where `ttl_cap` is a composition-root constant of **at most fifteen minutes** and `issued_at` is the broker seam's one clock read; `Validity` refuses an inverted window. A grant is **single use**: its id is derived from the request digest, so a second materialization for the same reservation returns the stored grant reference as a replay rather than minting another. |
| D-5 | Containment | **The secret never enters a canonicalised, digested or persisted structure.** A `CredentialGrant` is an opaque handle plus metadata; the grant store records only the handle reference, the request digest and the window, and the audit sink's ban on secret-bearing values applies. Consuming a grant is 5D's. **LIVE execution stays structurally blocked until 5D exists.** |

## Gaps that survive `[G]`

No resource vocabulary beyond Kubernetes-shaped targets; no revocation path for
an issued grant before expiry; no production broker implementation; 5D itself.

## Next step

Implement `cloud-scaling-credential-broker` against Risk Authority 0.8.0,
`cloud-scaling-action-admission` 0.1.0 and `execution-reservation` 0.1.0 under
D-1 … D-5, with the acceptance test issuing a grant for an admitted and reserved
action and refusing one for a `no_change` action, a released reservation, a
different target scope and a widened role.
