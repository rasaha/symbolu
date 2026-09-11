# Ugence Model Egress Provider — OpenAI Responses

**Version:** 0.1.1
**Maturity:** `REFERENCE_GRADE_SHADOW_ONLY` · `ENFORCEMENT_ENABLED = False` · `LIVE_VENDOR_EGRESS = False`
**Ruling basis:** LP-1, LP-3, LP-5 and LP-6 step 6 (`docs/architecture/ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md`, §0)

The OpenAI Responses adapter that the Model Egress Unit (MEU) will run behind once
commissioning reaches `MET`, shipped as a **separate, MEU-only distribution** so the
unit's own "cannot call a model vendor" claim stays intact.

## This distribution cannot reach api.openai.com

No HTTP client, no vendor SDK, no credential reader, no live network path. The
transport is **injected** — the adapter has no default — and the only transport this
package ships is `FakeTransport`, which never leaves the process, answers from a
script or with a labelled marker, and keeps of each dispatch a request digest and a
boolean `bearer_present`, never the bearer. `tests/test_boundaries.py` parses every
module and fails if one imports anything that could open a socket, reads the
environment, a clock or a file, or reaches into the unit's `postgres` subpackage.

Every record this package can produce carries `genuine_call: false`. A transport
that reports a genuine vendor response while commissioning is not `MET` is an
invariant violation: the adapter raises `GenuineResponseNotRecordable` rather than
write either a refusal (which would misstate a billed call) or a genuine record
(which the unit's release gate refuses). Fake-transport evidence therefore cannot
satisfy any live row of `MEU_LIVE_VALIDATION.json`.

## What is enforced, and where

| Ruling | Mechanism | Enforced at |
| --- | --- | --- |
| LP-1 / LP-3 exact destination | `PreparedRequest` accepts only `https://api.openai.com/v1/responses` via the unit's `check_destination`; `FakeTransport.send` asserts it again at the seam | construction; dispatch |
| LP-3 exact request shape | body keys are exactly `{model, input, max_output_tokens, store, stream}`; `store` and `stream` must be literally `false`; the model must be a dated snapshot | construction |
| LP-3 designated model | `gpt-5.4-mini-2026-03-17` only; an alias is `MODEL_NOT_PINNED`, another snapshot `MODEL_NOT_AVAILABLE` | pre-flight |
| LP-5 ceiling, second layer | `check_request` (8,192 input tokens, 1,024 output, no tools/streaming/store/background) then `CallBudget.reserve` (10 calls, USD 25, concurrency 1) **before** dispatch; nothing refunds | pre-flight; reserve |
| LP-5 retry | one retry, only for `TRANSIENT_BEFORE_DISPATCH` with the transport's `no_bytes_dispatched` proof; an unproven transient outcome is reclassified `DISPATCHED_NO_RESPONSE` and never retried | dispatch |
| §3.5 ambiguity | `DISPATCHED_NO_RESPONSE`, or a raising transport, records `OUTCOME_UNKNOWN` with a `DispatchAttempt` whose provider-side facts are `UNKNOWN` | record |
| Custody | a `CredentialLease` from the injected custody port; the secret is visible only inside `lease.use` for the one `transport.send` call | dispatch |
| Adapter cannot override | `limits` is a read-only property returning the frozen `COMMISSIONING_LIMITS`; a `CallBudget` under any other limits is refused at construction | construction |

The in-memory `CallBudget` is acceptable for unit tests and fake-transport
development only. Its durable twin — the exchange's `commissioning_budget` and
`commissioning_reservation` tables with trigger-enforced no-refund (MEU migration 2)
— is what a genuine call will reserve against; wiring the unit to reserve durably
in front of this adapter is LP-6 step 7 work.

## Dependency direction

```
ugence-model-egress-unit >= 0.3.0   (records, limits, destination, custody port)
        ▲
ugence-model-egress-provider-openai (this package)
```

One first-party dependency, no third-party one. The unit never imports this package;
`tests/test_boundaries.py` on both sides asserts it.

## Not in this distribution

- a live transport (LP-6 step 7, after the infrastructure designations);
- any credential, credential reader or Secret Manager client (LP-2);
- a `genuine_call: true` record (LP-4: only the owner's separate `MET` statement,
  released as a new version of the unit, admits one);
- verification that the designated model snapshot exists (ADR §0.2, divergence 5).

## Tests

```
cd packages/integration/model-egress-provider-openai
PYTHONPATH=src:../model-egress-unit/src python -m pytest
```

No database, no network, no clock. The suite proves the destination and shape
refusals, the pre-flight ordering the unit relies on, reserve-before-dispatch, the
proof-gated single retry, `OUTCOME_UNKNOWN` on every ambiguous path, the
eleventh-call refusal, that the leased secret appears in no record, state or repr,
and the one-way dependency.
