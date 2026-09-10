# Changelog — ugence-data-use-admission

## 0.3.0 — a declaration names the vocabulary each of its labels was written against

`CONTRACT_VERSION` moves to `data_use_admission.v2` and `SCHEMA_VERSION` to
`data_use_admission.sqlite.v2`. `ugence-governance-contracts` is untouched and its
`CONTRACT_VERSION` does not move, which is `VV-A` working as intended.

**Why.** A label recorded *what* a declarer called the data and left *under what
taxonomy* unrecorded, so an old declaration silently re-read under a new vocabulary.
Ballot `LV-1` §2 names that as one of four conditions blocking interpretation;
`VV-A` to `VV-E` scoped the fix and `PUB-2` authorized it, sequenced behind the
publication of the vocabularies themselves.

- `VocabularyBinding(vocabulary, version, specification_digest)` — one published
  vocabulary, named exactly. Package-local by `VV-A`: the binding lands on the record
  so that no new neutral type enters governance-contracts and `LP-5` is not pre-empted.
  A bare version string is refused, and so are `""`, `latest` and `current`.
- `DataUseDeclaration` gains `classification_vocabulary` and `purpose_vocabulary` —
  **two independent** bindings (`VV-D`), both **required** (`VV-E`). Purpose gets its
  own: `LV-E`'s open shape means the platform closes no member set, not that purpose
  terminology is anonymously sourced.
- Both are in `record_digest()` (`VV-B`) and in the derived `declaration_id` (`VV-C`,
  because these labels already participate in this record's identity). Two records
  identical but for the vocabulary version are now two records. **This is not additive
  and does not pretend to be**: `VV-B` accepted the compatibility consequence rather
  than leave authoritative semantics outside the digest.
- Re-declaring the same label under a new vocabulary version is an admissible
  supersession — the words are identical and what they were read to mean is not.
- **Records written before this still read.** A record with no stored version is v1 by
  construction, projects the v1 keys, and keeps the id and digest it was stored with
  (`VV-B`); it reports `UNVERSIONED_LEGACY` and is **never** resolved to a published
  vocabulary (`VV-E`). A v1 file opens read-only: appending to it would make its own
  schema row a lie, and migration needs its own ruled process.

**Still nothing interpreted.** Naming a vocabulary is not reading one. `DE-3` is
untouched: no taxonomy, no ordering, no comparison of members. The binding is recorded
and never resolved — this package does not open `docs/vocabularies/`, and a test
asserts it cannot.

**Two names differ from the published specification on purpose.** Its key is
`content_digest` and the field here is `specification_digest`, and the validation is
written in string operations rather than a regular expression, because this package's
payload guard forbids the identifier `content` and the `re` import outright. Both were
fixed at the coupling rather than by relaxing what the guard discriminates.

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
