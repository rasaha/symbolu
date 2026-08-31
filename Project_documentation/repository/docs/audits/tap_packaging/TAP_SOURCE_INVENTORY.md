# TAP source inventory

Machine-readable: `tap_source_inventory.json`.

| path | role | namespace | distribution | disposition |
|---|---|---|---|---|
| `packages/providers/tap/src/ugence_tap_provider` | CANONICAL_IMPLEMENTATION | `ugence_tap_provider` | `ugence-tap-provider` | canonical owner (one logic-bearing tree) |
| `tap_provider/` | COMPATIBILITY_SURFACE | `tap_provider` | shipped by `dgm-tap-provider` | logic-free facade + retained monorepo tests |
| `packaging/dgm-tap-provider` | PRIVATE_PACKAGING_ENTRY | — | `dgm-tap-provider` | converted to compatibility distribution → `ugence-tap-provider[decision-authority]` |
| `platform/api-snapshots/tap_provider.api.json` | FROZEN_API_ARTIFACT | — | — | byte-equivalent; preserved through facade |
| `docs/TAP_PROVIDER.md` | DOCUMENTATION | — | — | retained; canonical docs added under `packages/providers/tap/docs` |

No `STALE_OR_DUPLICATE` or `UNRELATED_USE_OF_TAP_NAME` implementation trees were
found. There is exactly one logic-bearing TAP source tree.
