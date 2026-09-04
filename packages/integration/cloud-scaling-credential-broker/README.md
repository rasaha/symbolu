# Ugence Cloud Scaling Credential Broker

**Cloud Scaling Phase 5X — short-lived, least-privilege credential brokering.**
Distribution `ugence-cloud-scaling-credential-broker` · namespace
`ugence_cloud_scaling_credential_broker` · version **0.1.0**.

> **A grant is a handle, not execution.**
> This package exchanges an admitted (5C) and reserved capacity action for a credential
> handle through a broker port, and stops there. It holds no provider secret to do it. 5D
> consumes the handle; LIVE execution stays structurally blocked until 5D exists.

Ratified by `docs/architecture/ADR_CLOUD_SCALING_PHASE5X_CREDENTIAL_BROKER_SCOPING.md`
(D-1 … D-5).

---

## What it composes

| Input | From | Role |
|---|---|---|
| `ActionAuthorization` (`AUTHORIZED`) | Risk Authority 0.8.0 `ActionAdmissionSeam` | what was admitted, loaded from the application |
| `ExecutionReservation` (`RESERVED`) | `execution-reservation` `reserve_once` | proof the action was cleared and reserved once |
| `ExecutionTargetScope` | Phase 5A, presented by the caller | re-derives the authorized action and the role |
| `CredentialBrokerPort` | a deployment's KMS, STS or vault adapter | custody, behind the port |

## The port (D-1)

`CredentialBrokerPort` mirrors the Trusted Evidence Authority signer port: `broker_authority_id`,
`credential_profile`, `is_production_authoritative`, and `materialize(request) -> CredentialGrant`.
The reference broker returns an inert handle and is refused in production. `os`, `sys`,
`secrets`, `socket`, `time`, `subprocess`, `urllib`, `http` and every cloud SDK are banned
over the AST and the dependency manifest.

## The request (D-2)

`CredentialRequest` is minted only by `CredentialRequestMinter`, behind a private token the
curated API does not export, from an `AUTHORIZED` authorization, a `RESERVED` reservation whose
execution key names that authorization and the authorized action digest, and a target scope
whose fixed D-2 mapping re-derives that digest. It binds the authorization ref, the execution
key, the target-scope digest, the reservation id, the envelope id, the derived role, the window
and a request digest over all of them.

## The role (D-3)

`derive_least_privilege_role(target_scope)` is a pure function: one operation from the action
type, one resource from account, compute group, resource class, namespace and region, and the
magnitude ceilings. `no_change` derives nothing. A broker may narrow the role and never widen
it; `role_widening` reports every dimension in which a granted role reaches beyond the derived one.

## The window (D-4)

`expires_at = min(authorization.expires_at, reservation.lease.expires_at, envelope.expires_at,
issued_at + ttl_cap)`, where `issued_at` is the seam's one clock read and `ttl_cap` is a
composition-root constant of at most **fifteen minutes**, enforced at construction. Grant ids
derive from the request digest; re-materializing the same request returns the stored grant as
`REPLAYED`.

## The grant (D-5)

`CredentialGrant` holds an opaque handle reference, the request digest, the role, the
`Validity` window and the broker identity. No field can carry secret material: field names
are checked against a denylist, no field is `bytes`, the handle reference is short printable
text, and the store persists only that. `tests/test_no_secret_material.py` asserts it.

## The act

```python
seam = CredentialBrokerSeam.production(app=app, reservations=ledger, broker=broker, grants=store,
                                       clock=clock, ttl_cap=timedelta(minutes=10))
out = seam.materialize(CredentialMaterializationRequest(
    tenant_id=..., authorization_id=..., reservation_id=..., target_scope=scope))
out.materialized   # a grant exists
out.replayed       # the stored grant was returned
out.executable     # always False
```

## Run the suite

```
python -m pytest packages/integration/cloud-scaling-credential-broker
```

The suite drives the genuine chain through the 5C fixtures and the execution ledger: an
issued envelope, an admitted action, a genuine `CLEAR` receipt from the Action Clearance
evaluator, a reservation, then a grant, its replay, and refusals for `no_change`, a released or
dispatched reservation, a different or wider target scope, a widened role, an expired
authorization and a ttl cap above fifteen minutes.
