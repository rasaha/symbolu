# Changelog — ugence-governance-provider-framework

All notable changes to the canonical Governance Provider Framework package.

## Unreleased — inclusive expiry boundary in the control-plane adapter (MAJOR)

`ActionGovernanceControlPlaneAdapter.authorize` now treats the expiry instant
itself as expired: `now >= cer.expires_at`, where it previously read
`cer.expires_at < now`.

This is a **fail-safe change to the framework**, not to any one provider. Every
action provider reached through this adapter is affected, including the
reference `DeterministicActionGovernanceProvider` and any third-party provider.
A CER evaluated at exactly its expiry instant previously authorized and now
returns `EXPIRED`.

Rationale: `ugence_action_clearance` applies the inclusive form in both places
it evaluates validity (`evaluation/__init__.py`, authorization validity and
signal validity). The exclusive form left a one-instant window in which
authorization and clearance disagreed about whether the same CER was live.

Provenance and scope — recorded because this hunk did not arrive through the
framework's own change record. It was authored inside the ActionGate vNext
commit `e32f9838`, whose deliberate hash re-baselining
(`core_tree_hashes["actiongate_provider"]`, the ActionGate `.api` snapshot,
`conformance_hashes[…ugence_actiongate_provider]`) covers ActionGate only. The
freeze does not hash this package at all: `core_tree_hashes["governance_providers"]`
covers the single-file legacy facade, so this change moved no frozen hash and
passed no freeze gate. It also arrived with no test in this package pinning the
boundary instant. Both gaps are closed here — see
`tests/integration/test_adapters.py::test_action_adapter_treats_the_expiry_instant_itself_as_expired`,
which fails against the exclusive form.

The rule is deliberately **not** shared with
`ugence_actiongate_provider.vnext.is_expired`, which states it identically: the
framework does not depend on a provider, and inverting that direction to share
four lines would be the worse trade. The rule is written twice; the test above
and ActionGate's own expiry tests are what keep the copies honest.

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
