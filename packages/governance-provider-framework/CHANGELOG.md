# Changelog — ugence-governance-provider-framework

All notable changes to the canonical Governance Provider Framework package.

## 0.1.0 — canonical-package migration (structural / PATCH)

Relocation of the capability-neutral Governance Provider Framework into its own
canonical package. **Zero semantic change, zero authority change, full backward
compatibility.**

### Changed (structural only)
- Canonical source tree moved from `governance_providers/` to
  `packages/governance-provider-framework/src/ugence_governance_provider_framework/`
  (history-preserving `git mv`). One physical implementation only.
- Canonical distribution `ugence-governance-provider-framework`; canonical
  namespace `ugence_governance_provider_framework`.
- The Decision Authority kernel dependency is now declared **optional**
  (extra `adapters`); the framework core installs and imports without it. No code
  or behaviour changed — only the packaging declaration. Importing `.api`/`.adapters`
  still requires the kernel facade, exactly as before.

### Preserved (identical)
- Public API `governance_providers.api` (48 symbols) — snapshot byte-identical.
- Registry, resolution, configuration, lifecycle, health, metadata, observability,
  fingerprints, versioning, conformance, and reference-provider behaviour.
- Error types and messages, public enum values, serialization.
- The legacy `governance_providers` namespace (top-level + deep imports) — now a
  logic-free, identity-preserving compatibility shim.
- The legacy `dgm-provider-framework` distribution — now a compatibility shell
  depending on this canonical distribution.

### Authority
- Unchanged. The framework owns no governance authority; concrete providers (TAP,
  ActionGate, baselines) remain separate packages.
