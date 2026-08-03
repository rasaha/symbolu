# Migrating to `ugence-tap-provider`

TAP's implementation moved from the monorepo `tap_provider/` tree to the canonical
package **`ugence-tap-provider`** (import namespace `ugence_tap_provider`,
`packages/providers/tap`). **No behavior changed** — only the package location.

## For consumers

No code change is required. The legacy `tap_provider` namespace is preserved as a
**logic-free compatibility facade** that re-exports the *identical* objects from
`ugence_tap_provider` (same classes, same modules, same serialization,
fingerprints, and errors). Both of these observe the same object:

```python
import tap_provider.api          as legacy   # keeps working, unchanged
import ugence_tap_provider.api   as canonical
assert legacy.TAPProvider is canonical.TAPProvider   # object identity preserved
```

New code should import from `ugence_tap_provider`.

## Distributions

| Distribution | Ships | Depends on |
|---|---|---|
| `ugence-tap-provider` (canonical) | `ugence_tap_provider` implementation | `ugence-governance-provider-framework` (core); `[decision-authority]` extra for the kernel-bound assessment integration |
| `dgm-tap-provider` (legacy, compatibility) | only the `tap_provider` facade | `ugence-tap-provider[decision-authority]==0.1.0` |

Installing only the canonical wheel provides `ugence_tap_provider`. Installing the
legacy compatibility wheel provides `tap_provider` and pulls in the canonical wheel
as a dependency. Installing both produces no file collision (the facade owns
`tap_provider`; the canonical wheel owns `ugence_tap_provider`).

## Versions

- **Implementation version**: `0.1.0` — unchanged by the relocation.
- **Canonical distribution version**: `0.1.0`.
- **Legacy compatibility distribution version**: `0.1.0`.
- **Contract version**: `1.0.0`; **mapping version**: `tap-map-1`.

`ugence_tap_provider.version_info()` reports all of these plus resolved dependency
versions and `production_certified = False`.

## Removal target

The `tap_provider` facade and the `dgm-tap-provider` compatibility distribution are
transitional, tracked for removal with the `tap_provider` 0.2.0 shim removal. Until
then, both remain fully supported.
