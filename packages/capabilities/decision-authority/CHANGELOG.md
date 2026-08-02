# Changelog — ugence-decision-authority

All notable changes to the canonical Decision Authority package.

## 1.0.0 — canonical-package migration

- **Relocated** the bounded Decision Authority kernel from the legacy
  `decision_governance` namespace into the canonical package
  `ugence_decision_authority` (distribution `ugence-decision-authority`), as a single
  independently packageable capability under
  `packages/capabilities/decision-authority`.
- **Zero semantic change.** Public API, binding-decision authority, tenant isolation,
  CER and decision semantics, segregation of duties, overrides, audit behavior, lifecycle,
  serialization, hashes/digests, error behavior, and frozen enums are unchanged. The frozen
  `decision_governance.api` public-API manifest hash is byte-identical
  (`1b893869…`).
- **Backward compatible.** The legacy `decision_governance` namespace remains available as a
  logic-free compatibility surface that re-exports the same objects (object identity
  preserved). The legacy `decision-governance` distribution becomes a compatibility shell
  depending on this package.
- **Relocation adjustment (necessary):** the conformance kit's "is this a kernel type"
  module-prefix check now recognizes the canonical namespace `ugence_decision_authority.`
  in addition to the legacy `decision_governance.` prefix. No behavior change for kernel
  records; purely an identity-path update required by the rename.

The public contract remains at the frozen **1.0.0**: no MAJOR change (no behavioral,
lifecycle, serialization, hash, port, removal/rename, or enum-value change).
