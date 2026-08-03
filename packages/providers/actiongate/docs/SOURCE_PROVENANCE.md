# ActionGate Source Provenance

History-preserving relocation of the ActionGate implementation from the monorepo
`actiongate_provider/` tree (commit `3b521f0f`) to the canonical package
`packages/providers/actiongate/src/ugence_actiongate_provider`. Machine-readable
data: `../artifacts/source_manifest.json` and `../artifacts/source_hashes.json`.

## Migration classification

| Type | Files | Notes |
|---|---|---|
| `BYTE_IDENTICAL` | 6 | `core.py`, `observability.py`, `api/__init__.py`, `client/__init__.py`, `mapping/__init__.py`, `mapping/constraints.py` — moved verbatim (they import only stdlib or package-relative names) |
| `IMPORT_ONLY_CHANGE` | 7 | `provider.py`, `configuration/__init__.py`, `conformance/__init__.py`, `errors/__init__.py`, `health/__init__.py`, `mapping/request.py`, `mapping/result.py` — only `governance_providers.api` → `ugence_governance_provider_framework.api` |
| `SEMANTIC_EXTRACTION` | 2 | `__init__.py` (canonical docstring + `version_info` re-export), `version.py` (added `DISTRIBUTION_VERSION`, `version_info()`, `VersionInfo`) |
| `NEW_PACKAGING_FILE` | 3 | `__main__.py`, `cli.py`, `py.typed` |
| **Total** | **18** | one logic-bearing tree; no duplicate implementation |

## Relocation method

`git mv` was used for every implementation file so blame/history follows the code.
The single mechanical edit applied after the move was the framework-import rewrite
(`governance_providers` → `ugence_governance_provider_framework`), verified to leave
zero remaining `governance_providers` references in the canonical tree.

## Equivalence evidence

- Public `.api` snapshot **byte-identical** to baseline (`9eeb66e3…`) through the
  legacy facade; canonical `.api` symbols identical (differ only by module-name
  label).
- Behavioral capture **before == canonical == legacy** (`d805e6cf…`).
- All 62 canonical package tests + 37 monorepo-integration tests pass.

## Provenance of the legacy namespace and distribution

- `actiongate_provider/__init__.py` — rewritten to a **logic-free facade** (no
  original implementation remains there). `LEGACY_SHIM`.
- `actiongate_provider/tests/*` — retained as the monorepo-integration view;
  `test_packaging.py` and `test_dependency_boundaries.py` updated for the new layout.
- `packaging/dgm-actiongate-provider/` — converted to a **compatibility
  distribution** depending on `ugence-actiongate-provider[decision-authority]==0.1.0`;
  the `actiongate_provider` entry remains a symlink to the root facade.
