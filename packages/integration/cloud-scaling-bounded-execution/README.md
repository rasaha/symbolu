# Ugence Cloud Scaling Bounded Execution

**Cloud Scaling Phase 5D — one bounded change per grant.**
Distribution `ugence-cloud-scaling-bounded-execution` · namespace
`ugence_cloud_scaling_bounded_execution` · version **0.1.0**.

> **The only path from a credential grant to the executor.**
> This package consumes a 5X `CredentialGrant` for a `RESERVED` execution reservation and
> dispatches exactly one bounded capacity change through Cloud Scaling Operations'
> `ControlledScalingExecutor`. `LIVE` survives only under a fully proven posture; any absence
> resolves to `dry_run` and **never simulation**. It holds no credential and builds no backend.

Ratified by `docs/architecture/ADR_CLOUD_SCALING_PHASE5D_BOUNDED_EXECUTION_SCOPING.md`
(D-1 … D-5).

---

## The act

1. one clock read; the executor is handed a clock that returns it, so it reads no wall clock;
2. load the grant, the authorization, its envelope and the reservation; refuse an unknown or
   expired grant, a non-`AUTHORIZED` authorization, a reservation that is not `RESERVED` or
   whose lease has lapsed;
3. **prove the grant** (D-2): re-mint the credential request through the 5X minter from the
   presented artifacts at the grant's own window and require its request digest to re-derive;
4. address the target (cluster = compute group, namespace = the scope's namespace or the
   account partition, resource = resource class) and the operation (`scale` for `scale_up`
   and `scale_down`; `no_change` and `coordinated` are not dispatchable);
5. **resolve the effective mode** (D-3) and **narrow the target policy** to the grant's role
   (D-4), never wider than the deployment's config;
6. **mint the operations-local `ExecutionAuthorization`** (D-1) with the seam as issuer,
   signed by a per-act verifier the seam constructs, bounds and delta from the role, target
   from the scope, and the execution key's serialized form as `idempotency_key` (D-2);
7. in an applying mode, `mark_dispatched` before the executor runs; execute **exactly one**
   bounded change; `record_observation` after with the outcome mapped (D-5);
8. mint the `BoundedExecutionRecord` and the RA-8 `EffectObservation`, persist the record,
   return. A second dispatch for the same grant and request id replays the stored record.

## LIVE gating (D-3)

| Precondition | Proven from |
|---|---|
| production Risk Authority application | `app._production_mode` |
| production-mode execution ledger | `SqliteExecutionReservationStore(production_mode=True)`; the in-memory ledger never |
| production-authoritative grant store and broker | their declarations; the reference broker never |
| non-reference grant handle | not the inert `inert:` prefix and not the reference broker's authority |
| injected backend | built by the deployment from the grant handle **outside this repository** |
| readiness required | `OperationsConfig.require_readiness` |

Any absence resolves `LIVE` to `dry_run`. `dry_run` proposes without touching the
reservation; `simulation` applies against the injected fake and advances the reservation.

## Blast radius and rollback (D-4)

`TargetPolicy` ceilings become `min(config, role)` and allowlists become the role's one target,
or nothing when the deployment's own allowlist excludes it. Rollback is a second bounded
action toward the prior record's `pre_state` with its own admission, reservation and grant;
`BoundedExecutionSeam.rollback` refuses a bare `RollbackPolicy` and refuses a foreign
`ExecutionAuthorization` too.

## The record (D-5)

`BoundedExecutionRecord` carries the grant, reservation, execution key, target-scope digest,
envelope and authorized action digest, `attempt_id` equal to the dispatch request id, the
effective mode and its reasons, the executor's outcome mapped to the effect vocabulary, pre and
post state, aware instants and the receipt hash. `effect_observation_for` mints the RA-8
`EffectObservation` from it; reconciliation stays RA-8's.

## Carried, not adopted

Cloud Scaling Operations' float clock and HMAC verifier are that dependency's. The seam
constructs a per-act verifier whose key is derived from the grant id and request digest; it
exists only so the executor's own signature gate runs unchanged and protects nothing across a
trust boundary.

## Run the suite

```
python -m pytest packages/integration/cloud-scaling-bounded-execution
```

The suite drives the genuine chain through the 5X fixtures: issued envelope, admitted action,
genuine `CLEAR` receipt, reservation, grant, then a dispatch in `simulation` against the fake
backend observed as `OBSERVED_SUCCESS`, the record and the observation, replay, every missing
LIVE precondition resolving to `dry_run`, a wider config narrowed to the role, and refusals for
a lapsed lease, an expired grant, a dispatched reservation, a mismatched target scope and a
bare-policy rollback.
