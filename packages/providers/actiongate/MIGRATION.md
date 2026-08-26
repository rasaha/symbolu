# Migrating to `ugence-actiongate-provider`

ActionGate's implementation moved from the monorepo `actiongate_provider/` tree to
the canonical package **`ugence-actiongate-provider`** (import namespace
`ugence_actiongate_provider`, `packages/providers/actiongate`). **No behavior
changed** — only the package location, and internal framework imports were rewritten
from `governance_providers.api` to `ugence_governance_provider_framework.api`.

## For consumers

No code change is required. The legacy `actiongate_provider` namespace is preserved
as a **logic-free compatibility facade** that re-exports the *identical* objects from
`ugence_actiongate_provider` (same classes, same modules, same serialization,
fingerprints, and errors). Both of these observe the same object:

```python
import actiongate_provider.api        as legacy   # keeps working, unchanged
import ugence_actiongate_provider.api as canonical
assert legacy.ActionGateProvider is canonical.ActionGateProvider  # object identity preserved
```

New code should import from `ugence_actiongate_provider`.

## Distributions

| Distribution | Ships | Depends on |
|---|---|---|
| `ugence-actiongate-provider` (canonical) | `ugence_actiongate_provider` implementation | `ugence-governance-provider-framework` (core); `[decision-authority]` extra for the kernel-bound control-plane integration |
| `dgm-actiongate-provider` (legacy, compatibility) | only the `actiongate_provider` facade | `ugence-actiongate-provider[decision-authority]==0.1.0` |

Installing only the canonical wheel provides `ugence_actiongate_provider`. Installing
the legacy compatibility wheel provides `actiongate_provider` and pulls in the
canonical wheel as a dependency. Installing both produces no file collision (the
facade owns `actiongate_provider`; the canonical wheel owns
`ugence_actiongate_provider`).

## Versions

- **Implementation version**: `0.1.0` — unchanged by the relocation.
- **Canonical distribution version**: `0.1.0`.
- **Legacy compatibility distribution version**: `0.1.0`.
- **Contract version**: `1.0.0`; **mapping version**: `actiongate-map-2`.

`ugence_actiongate_provider.version_info()` reports all of these plus resolved
dependency versions and `production_certified = False`.

## Dependency changes

The old `dgm-actiongate-provider` declared `decision-governance==1.0.0` and
`dgm-provider-framework==0.1.0`. ActionGate does **not** import `decision_governance`
directly (AST-verified), so that dependency is **dropped** from the core; the
framework dependency is renamed to the canonical `ugence-governance-provider-framework`.
The kernel is reached only through the framework's optional action control-plane
adapter, exposed here as the `decision-authority` extra.

## Removal target

The `actiongate_provider` facade and the `dgm-actiongate-provider` compatibility
distribution are transitional, tracked for removal with the `actiongate_provider`
0.2.0 shim removal. Until then, both remain fully supported.
