# Changelog — ugence-vendor-dependency

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

## 0.2.0 — the one ruled durable home (front-door ruling FD-13.2)

Authorized by `ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` §14.6 (FD-13.2
`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`, FD-13.4 `RISK_POSTURE_UNINTERPRETED`), on the
shape seam 8 proved for `data-use-admission` 0.2.0. **The contract surface is
unchanged**: `CONTRACT_VERSION` stays `vendor_dependency.v1`, and the new
`CONTRACT_MATURITY` records that the records, refusals, selectors and port are
exactly what 0.1.0 shipped.

- `SqliteVendorDeclarations`: one tenant-bound, append-only sqlite file implementing
  `VendorDependencyPort`, plus the single append `declare` — its only write. A plain
  file path under a writable volume: no server, no driver, no DSN, no network.
- The file is bound to one tenant at first open and **never re-bound**; a read or
  write naming another tenant is a typed refusal, never an empty answer.
- Append-only: a duplicate derived id is refused, an inadmissible supersession is
  refused by `supersession_refusals`, and nothing is ever edited or deleted.
- The record digest is re-verified on the way out, so a row altered outside the
  package cannot reconstruct.
- No clock: every `as_of` remains the caller's instant, so a lapsed declaration is
  absent from an answer without a sweeper.
- `declaration_record` / `declaration_from_record` and `binding_to_dict` /
  `binding_from_dict` make a declaration round-trip exactly, with the derived id
  re-verified on the way back in.
- New refusals: `DeclarationStorageError`, `DeclarationProductionModeError`,
  `DuplicateDeclarationError`, `CrossTenantRefused`.
- `MATURITY` becomes `CONTRACTS_PLUS_LOCAL_STORE`; `ENFORCEMENT_ENABLED` stays
  `False`.

**What did not change.** The posture is still uninterpreted (VR-3, FD-13.4): stored
verbatim, matched by exact text, and ordered, compared, ranked and scored nowhere. No
vendor approval, onboarding status, tier or certification exists to record, because
no package computes one. `vendor_ref` is still opaque, and `policy_ref` still
recorded and never resolved (VR-4). A declaration is still a record, not a
permission.

## 0.1.0 — wave 4, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_VENDOR_RISK_SCOPING.md`
(VR-1 to VR-5). Requires `ugence-governance-contracts>=0.7.0`, where the
`VendorRiskLabel` this package binds was landed first (VR-5).

- `VendorDependencyDeclaration`: a `tenant_id`, exactly one `AssessedSystemBinding`
  (VR-2) and one `VendorRiskLabel` (VR-3) re-exported from governance-contracts
  (never redefined), an opaque package-local `vendor_ref` (VR-5), one opaque
  `policy_ref` string (VR-4), a `Validity` window, an optional `supersedes`, and
  `declared_by`, `correlation_id`, `notes` annotations.
- A derived `declaration_id` — no UUID, no clock — bound to the binding's digest,
  the vendor reference, the label's digest, the policy reference and the window,
  **verified at construction**, so a caller can never choose one and two
  declarations can never collide.
- A `tenant_id` that disagrees with the binding's tenant is **refused**, never
  resolved either way; a look-alike binding or label is refused; a naive instant
  is refused; a bare string where the label type is expected is refused.
- `Validity`-bounded declaration evaluated with `status_at(as_of)`: outside its
  window a declaration is **absent from every answer**, not flagged. No clock is
  read anywhere, asserted over the AST.
- `supersession_refusals` / `require_admissible_supersession`: a superseding
  declaration must name its predecessor, stay in one tenant, concern the **same
  vendor**, and **change what was declared**. `supersession_chain` reconstructs
  history, walks only admissible links, and terminates on a cycle.
- `VendorDependencyPort`, a read-only Protocol with **no implementation**, and the
  pure selectors `declared_at`, `select_for_tenant`, `select_for_vendor`,
  `select_for_system`, `select_by_risk_posture`, `select_by_policy_ref`.
- Contracts only: no store, connector, gateway, scorer, questionnaire, network
  client or clock, asserted by boundary tests over module names and code
  identifiers. Structurally unable to resolve or verify a policy reference, score
  or grade risk, contact a vendor, persist a record, or import Policy Authority,
  Risk Authority or AI System Registry.
- Not an `…Authority`, `…Gateway`, `…Supplier` or `…Registry` (VR-1); no class of
  its own named `…SystemBinding` or `…Label` — asserted over the class definitions.
- Neighbours unmodified beyond governance-contracts 0.7.0: policy-authority,
  risk_authority, ai-system-registry 0.1.0, data-use-admission 0.1.0.
