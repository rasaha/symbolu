# Changelog — ugence-ai-system-registry

## 0.2.0 — front-door seam 5, the one ruled local store (FD-9.2, 2026-09-06)

Ruled by `docs/architecture/ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` §10.5.

- `SqliteSystemRegistry(path, *, tenant_id, production_mode=False)`: the one
  implementation of `SystemRegistryPort`, over a sqlite **file** in the seam-1
  posture (no server, driver, DSN or network), bound to exactly one tenant at
  construction and never re-bound. Its only write is `register`: append-only, a
  duplicate derived id refused, an inadmissible supersession refused by
  `supersession_refusals` (D-3), a foreign tenant refused on every read and write
  with `CrossTenantRefused`, never an empty answer. No edit, no delete. Every record
  is stored with its `record_digest` and re-verified on read; an altered record
  does not reconstruct. No clock is read; every `as_of` is the caller's.
- `binding_to_dict` / `binding_from_dict`, `registration_record` /
  `registration_from_record`: complete, reconstructible records; a neighbour's
  contract failure surfaces as this package's `ContractViolation`.
- Typed refusals: `RegistryStorageError`, `RegistryProductionModeError`,
  `DuplicateRegistrationError`, `CrossTenantRefused`.
- `MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"`; `CONTRACT_MATURITY = "CONTRACTS_ONLY"`
  for every module but `durable`. `ENFORCEMENT_ENABLED` stays `False`. D-5 stands:
  no systems-of-record connector, no admission, no gate, no attestation.
- Boundary tests now enumerate the one ruled store module and assert it imports
  sqlite and the standard library only.


## 0.1.0 — wave 2, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md`.

- `SystemRegistration`: one `AssessedSystemBinding` re-exported from
  governance-contracts (never redefined), an `owner_ref`, an uninterpreted
  `classification_label` (D-2), a `Validity` window and an optional `supersedes`.
- A derived `registration_id` — no UUID, no clock — bound to the binding's own
  canonical digest, so a different configuration or version can never share one.
- `Validity`-bounded registration evaluated with `status_at(as_of)`: outside its
  window a registration is **absent from every answer**, not flagged. No clock is
  read anywhere, asserted over the AST.
- `supersession_refusals` / `require_admissible_supersession` (D-3): a superseding
  registration must bind a different system identity, in the same tenant, naming its
  predecessor. `supersession_chain` reconstructs history, walks **only admissible
  links**, and terminates on a cycle.
- The derived `registration_id` is **verified at construction**, so a caller can
  never choose one and two registrations can never collide.
- `SystemRegistryPort`, a read-only Protocol with **no implementation** (D-4), and
  the pure selectors `registered_at`, `select_for_tenant`, `select_for_system`,
  `select_by_classification`.
- Contracts only (D-5): no store, adapter, connector or admission engine, asserted
  by boundary tests over module names and code identifiers.
- Not an `…Authority`, not a `…Portfolio`, and no class of its own named
  `…SystemBinding` — all three asserted over the class definitions.
- Neighbours unmodified: governance-contracts, agent-runtime, approval-workflow
  0.1.0, authority-directory 0.1.0.
