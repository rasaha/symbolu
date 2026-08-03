# Known Limitations

Ugence Procurement is a **reference workflow verified offline**, not a
production-ready system. The following limitations are deliberate and honestly
stated. None is a defect to be hidden — each marks the boundary of what this
distribution claims.

## Adapters and connectors

- The only supplier adapter is `SupplierExecutionAdapter` — a **deterministic,
  offline reference adapter**. It is not a real supplier or ERP connector.
- **No** production SAP Ariba, Coupa, ServiceNow, or Oracle connector ships.
- **No** network, credentials, or external I/O of any kind.

## Persistence

- Persistence is **in-memory only** (`InMemory*` repositories). Nothing survives
  process exit. There is no database, no durable audit store, no queue.

## Intelligence and autonomy

- **No** AI scoring model and **no** inference. Policy assessment and budget
  authority are fixed, deterministic, pure-function rules.
- **No** autonomous approval or autonomous purchasing behavior. A binding decision
  requires an authenticated human approver.

## Scope

- It is not an ERP, purchasing marketplace, inventory system, accounting system,
  or invoice/payment system. It does not manage inventory, do accounting, or
  process invoices/payments (see [PRODUCT_BOUNDARY.md](PRODUCT_BOUNDARY.md)).

## Validation and evidence

- **No** enterprise pilot has occurred; **no** production certification is claimed
  (`pilot_validated=False`, `production_certified=False`).
- The end-to-end behavior is a **deterministic simulation** of the governance
  lifecycle, verified offline — not evidence of live enterprise operation.

## Packaging / reproducibility

- The wheel is **bit-for-bit reproducible** under a fixed `SOURCE_DATE_EPOCH`, but
  the **sdist is content-reproducible, NOT bit-for-bit reproducible**. This is
  stated honestly rather than overclaimed.

## Transport surface

- The core `ugence_procurement.routes.ProcurementAPI` is framework-agnostic; the
  `api` extra (FastAPI/uvicorn) is **reserved for a future thin HTTP layer** and
  wraps no shipped endpoint today.

See [MATURITY.md](MATURITY.md) for the formal evidence classification and the
forbidden over-claims list.
