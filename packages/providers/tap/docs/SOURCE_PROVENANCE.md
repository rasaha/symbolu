# Source provenance

The canonical `ugence_tap_provider` tree was produced by a **history-preserving
relocation** (`git mv`) of the monorepo `tap_provider/` implementation, followed by
a mechanical import rewrite (`governance_providers.api` →
`ugence_governance_provider_framework.api`). No TAP evaluation logic was changed.

Baseline commit: `a3dfb69ef952e72c4a9c8e77d92b558b30ffec76`.

Full per-file record: `artifacts/source_manifest.json` (original path, original
commit, original blob SHA, canonical destination, current blob SHA, migration type)
and `artifacts/source_hashes.json` (canonical blob hashes).

## Migration-type summary (18 files)

| migration type | count | files |
|---|---|---|
| `BYTE_IDENTICAL` | 6 | `api/__init__.py`, `core/__init__.py`, `client/__init__.py`, `mapping/__init__.py`, `mapping/controls.py`, `observability/__init__.py` |
| `IMPORT_ONLY_CHANGE` | 7 | `provider.py`, `configuration/__init__.py`, `conformance/__init__.py`, `errors/__init__.py`, `health/__init__.py`, `mapping/request.py`, `mapping/result.py` |
| `SEMANTIC_EXTRACTION` | 2 | `__init__.py` (docstring + `version_info` export), `version.py` (added `DISTRIBUTION_VERSION` + `version_info()`) |
| `NEW_PACKAGING_FILE` | 3 | `cli.py`, `__main__.py`, `py.typed` |

The `IMPORT_ONLY_CHANGE` files differ from their originals **only** in the framework
import line. The `SEMANTIC_EXTRACTION` files add packaging metadata/CLI-support
surface without altering any evaluation logic. Equivalence is proven by the
byte-identical `.api` snapshot and the identical behavioral capture (before ==
canonical == legacy) recorded under `docs/audits/tap_packaging/artifacts/`.

There is **one** logic-bearing TAP source tree (`ugence_tap_provider`); the root
`tap_provider/__init__.py` is a logic-free facade.
