# Execution Key

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Defines the canonical key that binds a
one-time execution reservation. Aligns with the existing `execution_idempotency_key` in
`ugence_decision_authority` and the neutral `idempotency_key` on `ExecutionDispatchRequest`.

## Canonical execution key (decision)

```text
execution_key = ( tenant_id,
                  authorization_ref,
                  authorized_action_fingerprint,
                  target_ref,
                  operation )
```

This is exactly the merged replay key
(`Project_documentation/repository/docs/design/action_clearance/ONE_TIME_USE_AND_REPLAY.md`), promoted here to the canonical execution
reservation key. It **must be stable across retries** (an idempotent retry of the same authorized action
produces the same key) and **unique across distinct authorized actions** (any change to tenant,
authorization, action fingerprint, target, or operation yields a distinct key).

## Fields considered but excluded from the key identity

| Candidate | In the key? | Why |
|---|---|---|
| `tenant_id` | **yes** | isolation |
| `authorization_ref` | **yes** | binds to the specific authorization |
| `authorized_action_fingerprint` | **yes** | binds the exact action (SHA over action identity) |
| `target_ref` | **yes** | binds the target |
| `operation` | **yes** | binds the operation (e.g. `merge`) |
| `profile_id` | **carried, not in key** | already implied by `authorized_action_fingerprint`; carried as metadata for audit |
| `merge_method` | **carried, not in key** | folded into `authorized_action_fingerprint` for GitHub (a squash vs merge is a different action fingerprint) |
| `idempotency_key` | **derived from the key** | the ledger's `execution_idempotency_key` is a canonical serialization of the execution key |
| `clearance_receipt_ref` | **carried, not in key** | one lineage can re-issue receipts; the key must be stable across a fresh receipt for the same action, so the receipt ref is a *validated attribute*, not part of identity |

**Why `clearance_receipt_ref` is not in the key:** if the key included the receipt id, a re-issued
receipt (same action, fresher signals) would mint a *new* execution key and defeat one-time-use. The key
must identify the *authorized action*, not the *clearance evaluation*. The receipt ref is validated at
reservation time (`EXECUTION_RESERVATION_CONTRACT.md`) but is not part of the key's identity.

## Canonical serialization

The execution key is serialized with the same canonical rules as the fingerprints
(`SIGNAL_NORMALIZATION_AND_DIGESTS.md`): sorted, domain-separated, SHA-256, giving a stable
`execution_idempotency_key` string suitable for a uniqueness constraint. Proposed form:
`exec_key.v1:<sha256hex>`.

## Mapping to the existing ledger

`InMemoryExecutionRepository._idempotency` is keyed by `(tenant_id, execution_idempotency_key)`. The
`execution_idempotency_key` there **becomes** the canonical serialization of this execution key, so the
new reservation contract binds to the same index the ledger already maintains.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — the key is canonical and maps onto the existing
`execution_idempotency_key`. Schema: `execution_key.schema.json`.
