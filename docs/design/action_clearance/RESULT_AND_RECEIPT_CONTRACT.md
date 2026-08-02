# Result & Receipt Contract

Two distinct types, cleanly separated.

## `ClearanceResult` — deterministic evaluator output

Pure function of the request. No UUID, no clock read, no network, no persistence.

| Field | Required | Fingerprinted (in `result_fingerprint`) | Notes |
|---|---|---|---|
| `request_id` | yes | yes | echoes the caller-supplied id |
| `authorization_ref` | yes | yes | |
| `authorized_action_fingerprint` | yes | yes | |
| `status` | yes | yes | `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` |
| `reason_codes` | yes | yes (canonically ordered) | ordered by the canonical rule; order does not change the fingerprint |
| `effective_constraints` | yes | yes | `= authorization_constraints ∩ clearance_constraints` |
| `obligations` | yes | yes | `⊇ authorization_obligations` |
| `evaluated_at` | yes | yes | equals `request.evaluation_time` (caller-supplied) |
| `valid_until` | yes | yes | `≤ authorization.expires_at` and `≤ min(required-signal valid_until)` |
| `policy_refs` | yes | yes | |
| `signal_refs` | yes | yes | references/fingerprints of the signals evaluated |
| `request_fingerprint` | yes | yes | binds the result to its exact request |
| `result_fingerprint` | yes | n/a (it *is* the digest) | content address of all fingerprinted fields |

`result_id = "acr_" + result_fingerprint` (content-addressed; the `acr_` prefix is a hash label, not the
prohibited acronym).

## `ClearanceReceipt` — durable product record

Persisted by the caller/workflow layer around a `ClearanceResult`. It adds the nondeterministic /
storage metadata the evaluator must never generate.

| Field | Source | Fingerprinted? |
|---|---|---|
| `result` (embedded `ClearanceResult`) | evaluator | its own `result_fingerprint` |
| `receipt_id` | workflow layer (may be a UUID) | **excluded** from `result_fingerprint` |
| `issued_at` (wall clock) | workflow layer | **excluded** |
| `receipt_state` | workflow layer | **excluded** (see [`STATE_MACHINE.md`](STATE_MACHINE.md)) |
| `workflow_id` / `correlation_id` | request | carried for linkage |
| `superseded_by` | workflow layer | **excluded** |
| `dispatch_linkage_ref` | execution ledger | **excluded** |

## Why two types

- `ClearanceResult` is **deterministic**: the same request always yields byte-identical fingerprinted
  content, enabling replay, equivalence testing, and content-addressed linkage.
- `ClearanceReceipt` is **durable and product-shaped**: it may carry UUIDs, wall-clock issue time, and
  mutable lifecycle state — none of which the evaluator may produce, and all of which are **excluded**
  from `result_fingerprint` so storage metadata never perturbs the evaluation identity.

## Identity strategy (chosen)

**Caller-supplied `request_id` + content-addressed `result_id`.**

- `request_id` is supplied by the caller (idempotent retries reuse it).
- `result_id` is `acr_<result_fingerprint>` — a deterministic content address; the same request produces
  the same `result_id`.
- The evaluator generates **no** nondeterministic UUID and reads **no** system clock; any UUID or
  wall-clock lives only on the `ClearanceReceipt` (workflow layer).

This is the deterministic combination the prompt asks for, and it makes "caller retries identical
request → identical result fingerprint" (acceptance scenario 18) hold by construction.

Machine-readable: [`action_clearance_result.schema.json`](action_clearance_result.schema.json).
