# Changelog — ugence-ai-system-registry

## 0.3.0 — a registration names the vocabulary its classification label was written against

`CONTRACT_VERSION` moves to `ai_system_registry.v2` and `SCHEMA_VERSION` to
`ai_system_registry.sqlite.v2`. `ugence-governance-contracts` is untouched and its
`CONTRACT_VERSION` does not move, which is `VV-A` working as intended.

**The ruling that shapes this package is `VV-C`, and it says no.** The binding goes into
`record_digest()` and deliberately **not** into the derived `registration_id`: this
record's identity is the system binding, the owner and the window, and the label never
took part in it. `VV-C` rejected the binary framing that would have given all four
packages one answer — the binding follows the label, and here the label is descriptive.
So every existing registration id is unchanged, and two registrations differing only in
vocabulary version share an id and differ in digest.

- `VocabularyBinding(vocabulary, version, specification_digest)` — one published
  vocabulary, named exactly. Package-local by `VV-A`, and copied from
  `data-use-admission` rather than shared, exactly as `_canon.py` is: four identical
  copies is the price `VV-A` chose in exchange for `governance-contracts` gaining no
  type and `LP-5` not being pre-empted.
- `SystemRegistration.classification_vocabulary` is **required** on a v2 record
  (`VV-E`). `""`, `latest` and `current` are refused by name.
- **Records written before this still read.** A record with no stored version is v1 by
  construction, projects the v1 keys, and keeps the digest it was stored with; it
  reports `UNVERSIONED_LEGACY` and is never resolved to a published vocabulary. A v1
  file opens read-only — migration needs its own ruled process.

**Still nothing interpreted.** Naming a vocabulary is not reading one. `D-2` is
untouched: no taxonomy, no ordering, no severity, no recognized set. The binding is
recorded and never resolved — this package does not open `docs/vocabularies/`, and a
test asserts it cannot.


## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

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
