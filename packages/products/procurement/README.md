# Ugence Procurement

**Governed purchase approvals and authorized supplier actions.**

Ugence Procurement is a bounded governance vertical built on the domain-neutral
Decision Authority kernel (`ugence-decision-authority`). It walks a purchase request
through a complete, audited governance lifecycle and enforces — in types, services,
persistence, and API, not merely in documentation — the hard separation between
advisory recommendations and binding human decisions, and between an authorized
purchase and its actual execution.

```
purchase request → deterministic validation → deterministic policy assessment
→ advisory recommendation → HUMAN approval decision → governed action request
(exactly bound to the approved supplier / budget / amount) → neutral authorization
→ EXPLICIT supplier dispatch → observed supplier outcome → reconciliation
→ compensation (when required)
```

## What it is not

Ugence Procurement is **not** an ERP, purchasing marketplace, inventory system,
accounting system, invoice/payment system, or autonomous purchasing agent. It ships
**no** AI scoring model, **no** autonomous approval, and **no** production SAP Ariba,
Coupa, ServiceNow, or Oracle connector. The included supplier adapter is
**deterministic and offline**. No live enterprise pilot has occurred and no
production certification is claimed (`version_info().pilot_validated == False`,
`version_info().production_certified == False`).

## Install

```bash
pip install ugence-procurement
```

Core dependencies are minimal: `pydantic>=2` and `ugence-decision-authority>=1.0.0`.

## Use

```python
from ugence_procurement.api import (
    build_in_memory_platform, ProcurementAPI, ProcurementConfiguration,
    PurchaseRequest, PurchaseItem, SupplierReference, BudgetReference,
    PurchaseRecommendation, PurchaseApproval, version_info,
)

platform = build_in_memory_platform()
# … register principals, publish mappings, then drive ProcurementAPI(platform).run(...)
```

## CLI

```bash
ugence-procurement version     # distribution + product version/maturity metadata
ugence-procurement verify      # assert safety/governance invariants (PASS/FAIL)
ugence-procurement demo        # deterministic reference lifecycle + fail-closed case
ugence-procurement report      # structured JSON report of the demo cohort
# equivalently: python -m ugence_procurement <command>
```

## Backward compatibility

The legacy `domains.procurement` and `applications.procurement` import paths keep
working through logic-free compatibility facades that re-export the identical
canonical objects (object identity preserved).

## Maturity

Product evidence: **REFERENCE_WORKFLOW_OFFLINE_VERIFIED** — the full reference
workflow is verified offline and deterministically. Ready for *bounded shadow-pilot
design*, not for pilot or production use. See [`docs/MATURITY.md`](docs/MATURITY.md).

## Documentation

See [`docs/`](docs/): architecture, product boundary, authority model, lifecycle,
dependency graph, public API, compatibility, determinism, security/failure model,
integration ports, known limitations, maturity, migration, rollback, and next phases.
