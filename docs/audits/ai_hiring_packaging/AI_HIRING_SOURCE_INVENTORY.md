# AI Hiring — Source Inventory

Machine-readable: [`ai_hiring_source_inventory.json`](ai_hiring_source_inventory.json).

## Canonical source tree
**`ai_hiring/`** — 302 `.py` files across 30 subpackages. Selected by
**import-direction analysis**, not directory name:

- `domains/hiring/*` imports `ai_hiring.*` (re-export surface).
- `applications/ai_hiring/platform.py` imports `domains.hiring.*` and
  `decision_governance.*` (composition root).
- `ai_hiring/__init__.py` documents itself as the historical implementation
  retained for import stability.

So the concrete implementation lives under `ai_hiring/`; the other two are thin
layers built on top of it.

## Duplicate / re-export / composition layers (not independent implementations)
| Path | Role | Classification |
|---|---|---|
| `domains/hiring/` | canonical hiring-domain re-export surface | RE_EXPORT_SURFACE |
| `applications/ai_hiring/` | composition root (wires domain + kernel) | COMPOSITION_ROOT |

## Public surface
- Public imports: `ai_hiring.HiringPlatform`, `ai_hiring.build_in_memory_platform`,
  `ai_hiring.__version__`.
- CLI: `python -m ai_hiring.product` (`version` / `demo` / `report` / `verify`).
- Product version source of truth: `ai_hiring/product/version.py` (`PRODUCT_VERSION="0.6.0"`).
- Release-manifest source of truth: `docs/ai-hiring/release/RELEASE_MANIFEST.md`.

## Downstream consumers of `import ai_hiring` (outside `ai_hiring/`)
6 files, all monorepo composition/domain layers, **classified
`KEEP_COMPATIBILITY_IMPORT`** (unchanged in this PR):
`applications/ai_hiring/platform.py`, `domains/hiring/{__init__,adapters,errors,repositories,services}.py`.

No mass edits were performed. Migrating these would alter platform-frozen trees;
they are preserved and continue to resolve the historical `ai_hiring` source.

## Governance dependencies (already extracted)
- `decision_governance.*` → canonical `ugence_decision_authority`
  (`packages/capabilities/decision-authority/src`).
- `governance_providers.*` → canonical `ugence_governance_provider_framework`
  (`packages/governance-provider-framework/src`).
- Both depend on `ugence-governance-contracts`.
