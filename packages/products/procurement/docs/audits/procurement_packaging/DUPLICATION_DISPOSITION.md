# Procurement Duplication Disposition

## Principle: one canonical physical implementation

All procurement business logic lives exactly once, under
`packages/products/procurement/src/ugence_procurement/`.

## Legacy trees become logic-free facades

| Legacy path | After extraction |
|---|---|
| `domains/procurement/__init__.py` | Logic-free facade: aliases the canonical **domain** submodules (`errors`, `requests`, `validation`, `policies`, `approvals`, `actions`, `suppliers`, `adapters`) into `sys.modules` under `domains.procurement.*` (object identity preserved). |
| `domains/procurement/{requests,policies,…}/**` | **Deleted** — resolved via the facade alias, not duplicated. |
| `applications/procurement/__init__.py` | Logic-free facade: aliases `ugence_procurement.configuration` / `ugence_procurement.platform`; re-exports `ProcurementPlatform`, `build_in_memory_platform`, `ProcurementConfiguration`. |
| `applications/procurement/api/__init__.py` | Logic-free facade: aliases `applications.procurement.api.routes → ugence_procurement.routes`; re-exports `ProcurementAPI`, `ProcurementRunResult`. |
| `applications/procurement/{configuration,platform}.py`, `api/routes.py` | **Deleted** — resolved via the facade alias. |
| `domains/procurement/tests/**` | **Kept** — now doubles as the legacy compatibility suite, exercising the facades. |

## Verification

* Object identity: `ugence_procurement.<x> is domains.procurement.<x>` and
  `… is applications.procurement.<x>` for every migrated symbol (tested).
* No second implementation: the compatibility modules contain only import/alias
  statements and re-exports — no class, function, or policy body.
* Behavior: `before == canonical == legacy` (see `PROCUREMENT_LIVE_AUDIT.md`).
