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
- The Decision Authority kernel dependency is now **optional** (extra `adapters`).
  As an optional-dependency **boundary correction** for the new canonical
  distribution, the three kernel-bound adapters load Decision Authority **lazily**
  (at invocation), so the framework core AND the canonical public API
  `ugence_governance_provider_framework.api` — including the adapter symbols —
  import without Decision Authority installed. Only *invoking* an adapter requires
  the `adapters` extra; doing so without it raises a precise error naming
  `ugence-governance-provider-framework[adapters]`. When the extra is installed,
  adapter behaviour is byte-for-byte identical. This is a packaging/import-boundary
  correction only — no governance behaviour, authority, public signature, field,
  enum, error, or serialization changed, and the frozen `governance_providers.api`
  snapshot remains byte-identical.

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
