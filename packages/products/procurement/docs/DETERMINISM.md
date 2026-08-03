# Determinism

Every stage of the Ugence Procurement workflow is **deterministic and offline**.
There is no inference, no scoring model, no randomness, and no external I/O. The
same inputs always produce the same records.

## Why deterministic

- **Policy assessment** (`ProcurementAssessmentService`) runs a fixed set of pure-function checks (`budget_exists`, `supplier_exists`, `required_fields_complete`, `justification_present`, `amount_calculated`, `budget_sufficient`). No inference, no scoring, no autonomous approval.
- **Budget authority** (`BudgetAuthorityAdapter`) classifies in a fixed order with no randomness: `EXPIRED` → restricted-supplier/budget `DENIED` → over-`hard_limit` `DENIED` → over-`approval_threshold` `AUTHORIZED_WITH_CONSTRAINTS` → else `AUTHORIZED`. The result is a pure function of the action request, its CER, and configured limits.
- **Supplier execution** (`SupplierExecutionAdapter`) is rule-based: transport-failing action types → `TRANSPORT_FAILED`; timing-out types → `TIMED_OUT`; otherwise `ACKNOWLEDGED` with a deterministic external id. `query_status` returns the configured outcome (default `ACCEPTED`).

## Offline: no network, credentials, or external state

The package ships only deterministic, offline reference adapters. No procurement
code path opens a socket, reads a secret, or touches an external system.
Persistence is in-memory only. The configuration holds tunable limits and
registries — no endpoints, no secrets.

## Behavior-capture equivalence

A deterministic behavior capture (`scripts/capture_behavior.py`) records
representative outcomes across the scenario matrix — valid and budget-insufficient
assessments, the validation error taxonomy, action mappings, the happy-path
end-to-end run, above-threshold constrained authorization, restricted-supplier and
hard-limit fail-closed denials, the supplier outcome vocabulary, and the
audit-event sequence — with all volatile ids and timestamps masked.

Captured against the original pre-extraction source, the canonical
`ugence_procurement`, and the legacy facades, all three hashes match:

```
before    : 541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
canonical : 541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
legacy    : 541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
```

**`before == canonical == legacy`** — the extraction preserved behavior exactly,
and the determinism makes that equality reproducible on demand.

## Consequence

Determinism is what makes the maturity classification
`REFERENCE_WORKFLOW_OFFLINE_VERIFIED` honest and the `verify` / `demo` / `report`
CLI commands reproducible. It also means the workflow can be re-run anywhere,
offline, with no configuration of external systems. See
[SECURITY_AND_FAILURE_MODEL.md](SECURITY_AND_FAILURE_MODEL.md) for how uncertainty
is handled fail-closed.
