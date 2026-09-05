# Changelog — ugence-vendor-dependency

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
