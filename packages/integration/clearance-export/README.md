# Ugence Clearance Export

`ugence-clearance-export` — the portable, content-addressed form of a clearance receipt
a deployment **received**.

> **This package serializes a clearance somebody else evaluated and reports what a
> reader can check about it. It never clears, authorizes, approves, signs, mints,
> stores or decides.**

Scoped and ratified by
[`ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md`](../../../docs/architecture/ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md)
§10 (CE-1 to CE-5) and §13 (CE-6, CE-7).

**Contracts only.** A record type, three one-member enums, refusal reasons, pure
selectors, one read-only Protocol and one pure verifier. No store, no adapter, no
connector, no clock, no network — so an export cannot reach a clearance evaluator, a
policy, a key or a runtime, and the lines the rulings draw are held structurally rather
than by discipline.

## What the artifact says about itself

Three claims, each with exactly one admissible value, because exactly one thing is
establishable in each dimension today:

| Field | Value | Why one member |
|---|---|---|
| `identity_assurance` | `PRESENTED_UNPROVEN` | Every declarer upstream of a clearance presented an identity nothing verified. A verified assurance needs an enterprise issuer that does not exist (CE-3). |
| `authenticity` | `UNSIGNED` | Content-addressing establishes integrity, never authenticity. A `TrustAnchorResolverPort` exists in `trusted-evidence-authority` and no signing key or trust root is configured (CE-4). |
| `data_classification` | `SYNTHETIC_DEMONSTRATION_ONLY` | The deployment holds no clearance any authority granted. A seeded receipt exercises the export path and the verifier and is evidence about nothing else (CE-7, §13.1). |

None of the three may be inferred from the absence of another. All three are **required
keyword arguments**, validated against the single admissible value, always serialized,
and inside the fingerprint preimage — so stripping one is detected exactly as an altered
decision is detected. A payload that dropped a label is refused, never defaulted.

## Verification reports; it does not bless

`verify_export()` returns an `ExportVerification`, not a boolean. It confirms the
artifact is intact, and in the same breath names the four things intact does not mean:

```
AUTHENTICITY_NOT_ESTABLISHED     nothing signed this
DECLARER_IDENTITY_NOT_VERIFIED   every upstream identity is PRESENTED_UNPROVEN
POLICY_IN_FORCE_NOT_CHECKABLE    policy_refs resolve only against the producing deployment
APPROVAL_NOT_PROVEN              authorization_ref is a reference, not a proof
```

`report.confers` answers the question a consumer actually has, and the answer is
`NOTHING`: verification grants no permission, satisfies no obligation, and is not an
authority's decision that any action may proceed.

Both layers are checked. An artifact whose wrapper is intact and whose clearance was
swapped is not intact.

## Exporting is not clearing

A compile result establishes *what was compiled*. A clearance establishes *whether a
consequential action may proceed now, and until when*. `build_export()` accepts only a
`ClearanceReceiptBody`, and the reconstruction path refuses compile-shaped keys
(`logical_digest`, `workflow_ir`, `compiled_at`, `compilation_id`) outright — so the two
questions cannot be collapsed into one artifact by accident (CE-1).

## Export is a read

`ReceivedClearanceSource` has two methods, `read_receipt` and `list_receipt_ids`. It has
no write, and this package exposes no verb that accepts a receipt (CE-5, §13.3).

## Dependency direction

One-way, and one dependency. `action-clearance` is not extended: its receipt body is
re-serialized here and gains no field and no transport concern from being exported
(CE-2). `ugence-execution-reservation` is deliberately **not** a dependency — it
persists receipts, and a store reached through the dependency graph is still a store.

```
ugence-action-clearance   <- ClearanceReceiptBody / ClearanceResult / ClearanceStatus
    ▲
ugence-clearance-export (this package)
```

## Tests

```bash
python -m pytest packages/integration/clearance-export/tests -q
```
