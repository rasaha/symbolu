# Changelog — ugence-data-use-admission

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
