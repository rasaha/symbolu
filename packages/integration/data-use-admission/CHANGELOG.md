# Changelog — ugence-data-use-admission

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

## 0.2.0 — the one ruled local home (front-door seam 8, ruling FD-12.2)

The record shape is unchanged and still contracts-only (`CONTRACT_MATURITY`); what is
new is where a declaration lives. `MATURITY` becomes `CONTRACTS_PLUS_LOCAL_STORE`.

- `SqliteDataUseDeclarations(path, tenant_id=..., production_mode=False)`: one
  tenant-bound, append-only sqlite file implementing the read-only
  `DataUseDeclarationPort` plus the single append `declare` (FD-12.5). A plain file
  path under a writable volume: no server, no driver, no DSN, no network.
- Bound to one tenant at first open and **never re-bound**: a file bound to another
  tenant is `CrossTenantRefused` before any read, and a read or write naming another
  tenant is a typed refusal, never an empty answer.
- Append-only: a duplicate derived id is `DuplicateDeclarationError`, a supersession is
  admitted only by `supersession_refusals`, and there is no edit, delete, admit,
  authorize, classify or enforce method. A record altered outside the package fails its
  digest check on read (`ContractViolation`).
- `production_mode=True` refuses an in-memory or URI location
  (`DeclarationProductionModeError`); storage faults are `DeclarationStorageError`.
- `declaration_record` / `declaration_from_record` and `binding_to_dict` /
  `binding_from_dict`: the complete, reconstructible record, with the derived id
  re-verified on the way back in.
- Every semantic prohibition still holds, mechanically: the store keeps the reference
  and never the data, leaves the classification and residency labels uninterpreted
  (DE-2, DE-3), reads no clock, and names no network. `tests/test_durable.py` pins all
  of it, and the contracts-only boundary scans now enumerate `durable.py` as the one
  ruled store rather than being relaxed.

## 0.1.0 — wave 4, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md`
(DE-1 to DE-5). Requires `ugence-governance-contracts>=0.6.0`, where the
`DataClassificationLabel` this package binds was landed first (DE-5).

- `DataUseDeclaration`: a `tenant_id`, one `AssessedSystemBinding` and one
  `DataClassificationLabel` re-exported from governance-contracts (never
  redefined), an opaque non-secret `data_ref`, an uninterpreted `purpose_label`,
  a `Validity` window, recorded-only `residency_label` metadata (DE-2), an
  optional `supersedes`, and `declared_by`, `correlation_id`, `notes` annotations.
- A derived `declaration_id` — no UUID, no clock — bound to the binding's digest,
  the data reference, the label's digest, the purpose and the window, **verified at
  construction**, so a caller can never choose one and two declarations can never
  collide.
- A `tenant_id` that disagrees with the binding's tenant is **refused**, never
  resolved either way; a look-alike binding or label is refused; a naive instant
  is refused.
- `Validity`-bounded declaration evaluated with `status_at(as_of)`: outside its
  window a declaration is **absent from every answer**, not flagged. No clock is
  read anywhere, asserted over the AST.
- `supersession_refusals` / `require_admissible_supersession`: a superseding
  declaration must name its predecessor, stay in one tenant, concern the **same
  data**, and **change what was declared** — an unchanged declaration has nothing
  to supersede. `supersession_chain` reconstructs history, walks only admissible
  links, and terminates on a cycle.
- `DataUseDeclarationPort`, a read-only Protocol with **no implementation**, and
  the pure selectors `declared_at`, `select_for_tenant`, `select_for_data`,
  `select_for_system`, `select_by_classification`, `select_by_purpose`.
- Contracts only: no store, adapter, connector, proxy, redactor, minimizer,
  classifier, network client or clock, asserted by boundary tests over module
  names and code identifiers. Structurally unable to inspect a payload (no field
  can carry one), admit data into a context, authorize an action, select a model,
  evaluate residency or govern result egress.
- Not an `…Authority` (DE-4); no class of its own named `…SystemBinding` or
  `…Label` — asserted over the class definitions.
- Neighbours unmodified beyond governance-contracts 0.6.0: context-minimization,
  actiongate, model-selection, ai-system-registry 0.1.0.
