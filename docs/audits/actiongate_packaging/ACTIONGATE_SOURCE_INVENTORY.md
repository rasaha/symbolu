# ActionGate Source Inventory

Every ActionGate surface located in the live tree, classified. Blob SHAs are from
commit `3b521f0f` (audit start). Full data: `actiongate_source_inventory.json`.

## Logic-bearing implementation (the ONE canonical tree)

All under `actiongate_provider/` (distribution `dgm-actiongate-provider`, import
namespace `actiongate_provider`). After migration this tree becomes a **logic-free
facade** and the single logic-bearing tree is
`packages/providers/actiongate/src/ugence_actiongate_provider`.

| Path | Role | Logic | Blob |
|---|---|---|---|
| `actiongate_provider/__init__.py` | CANONICAL_IMPLEMENTATION | pkg | `a0403938` |
| `actiongate_provider/version.py` | CANONICAL_IMPLEMENTATION | yes | `147f8f9c` |
| `actiongate_provider/core.py` | CANONICAL_IMPLEMENTATION | yes (engine) | `d63a2751` |
| `actiongate_provider/provider.py` | CANONICAL_IMPLEMENTATION | yes (adapter) | `05180c5f` |
| `actiongate_provider/observability.py` | CANONICAL_IMPLEMENTATION | yes | `e938eef8` |
| `actiongate_provider/api/__init__.py` | CANONICAL_IMPLEMENTATION | re-export | `006ff911` |
| `actiongate_provider/client/__init__.py` | CANONICAL_IMPLEMENTATION | yes | `7f6b137b` |
| `actiongate_provider/configuration/__init__.py` | CANONICAL_IMPLEMENTATION | yes | `8e7cb5ee` |
| `actiongate_provider/conformance/__init__.py` | CANONICAL_IMPLEMENTATION | yes | `930bba99` |
| `actiongate_provider/errors/__init__.py` | CANONICAL_IMPLEMENTATION | yes | `db9b2bf4` |
| `actiongate_provider/health/__init__.py` | CANONICAL_IMPLEMENTATION | yes | `47d80050` |
| `actiongate_provider/mapping/__init__.py` | CANONICAL_IMPLEMENTATION | re-export | `ad2b8f7e` |
| `actiongate_provider/mapping/request.py` | CANONICAL_IMPLEMENTATION | yes | `df692f3c` |
| `actiongate_provider/mapping/result.py` | CANONICAL_IMPLEMENTATION | yes | `9fe53d02` |
| `actiongate_provider/mapping/constraints.py` | CANONICAL_IMPLEMENTATION | yes | `1c8b8a54` |
| `actiongate_provider/tests/*.py` (7) | TEST | — | see JSON |

## Private packaging entry

| Path | Role |
|---|---|
| `packaging/dgm-actiongate-provider/pyproject.toml` | PRIVATE_PACKAGING_ENTRY |
| `packaging/dgm-actiongate-provider/actiongate_provider` | PRIVATE_PACKAGING_ENTRY (symlink → root tree) |
| `packaging/verify_independent_distribution.py` | PRIVATE_PACKAGING_ENTRY (verifier) |

## Frozen API artifact

| Path | Role |
|---|---|
| `platform/api-snapshots/actiongate_provider.api.json` | FROZEN_API_ARTIFACT |
| `platform/PLATFORM_FREEZE_V1.json` (actiongate entries) | FROZEN_API_ARTIFACT |

## Framework / application adapters (consumers — not moved)

| Path | Role |
|---|---|
| `governance_providers` control-plane adapter (`ActionGovernanceControlPlaneAdapter`) | FRAMEWORK_ADAPTER (owned by the framework package, not ActionGate) |
| `products/code-governance/.../actiongate_adapter.py` | APPLICATION_ADAPTER |
| `packages/products/ai-hiring/.../actiongate_legacy_adapter.py` | APPLICATION_ADAPTER (AI Hiring — not modified) |
| `ugence_console_api/capabilities/action_control.py` | APPLICATION_ADAPTER |

## Documentation

`docs/ACTIONGATE_PROVIDER.md` and the many root `ACTIONGATE_*.md` briefs are
DOCUMENTATION (product/marketing) — untouched by this migration.

## Stale / duplicate

**None.** There is exactly one logic-bearing ActionGate implementation
(`actiongate_provider/`). No duplicate or shadow implementation exists. After
migration there remains exactly one logic-bearing tree (the canonical package);
the legacy namespace becomes a facade.
