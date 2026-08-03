# Maturity

Ugence Procurement carries a deliberately **conservative** maturity
classification. The metadata is machine-readable via `version_info()` and
`product_maturity()`, and the hard flags cannot be flipped by documentation.

## Evidence classification

| Field | Value |
|---|---|
| Product version | `0.1.0` |
| Distribution version | `0.1.0` |
| Platform baseline | `v1.0` (Decision Authority kernel) |
| Stability | `pre-1.0 / reference-workflow` |
| Evidence maturity | `REFERENCE_WORKFLOW_OFFLINE_VERIFIED` |
| Readiness | `READY_FOR_BOUNDED_SHADOW_PILOT_DESIGN` |
| `pilot_validated` | **False** (hard-coded) |
| `production_certified` | **False** (hard-coded) |

## What `REFERENCE_WORKFLOW_OFFLINE_VERIFIED` means

The **full reference workflow** — request → validation → assessment →
recommendation → human decision → action → authorization → dispatch → outcome →
reconciliation → compensation — is verified **offline and deterministically**. The
behavior is reproducible and equivalence-proven (see [DETERMINISM.md](DETERMINISM.md)).

## What it does NOT mean

It does **not** mean the product has been piloted, validated with real data,
integrated with any enterprise system, or certified for production. Offline
verification of a deterministic reference workflow is exactly that — no more.

## Readiness note

`READY_FOR_BOUNDED_SHADOW_PILOT_DESIGN` is a forward-looking note about what could
be **designed** next (a bounded, controlled shadow pilot). It is explicitly **not**
a validation claim and does not assert readiness to run a pilot or to operate in
production.

## Hard flags

`pilot_validated` and `production_certified` are hard-coded `False` in
`ugence_procurement.product.version` and surfaced by `version_info()`. They ship
`False` because the package contains only deterministic, offline reference
adapters and makes no production, scale, or enterprise-integration claim.

## Forbidden over-claims

The following must **never** be claimed for this distribution:

- `PILOT_VALIDATED`
- `PRODUCTION_VALIDATED`
- `PRODUCTION_READY`
- `ERP_READY`
- `AUTONOMOUS_PROCUREMENT_READY`

`RELEASE_CLASSIFICATION = "INDEPENDENT_PACKAGE_VERIFIED"` is a packaging aspiration
about the wheel's extraction gates; it is **not** a product-maturity claim. The
honest product-evidence classification remains
`REFERENCE_WORKFLOW_OFFLINE_VERIFIED`.
