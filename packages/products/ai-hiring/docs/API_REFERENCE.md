# API Reference

## Public top-level API

Importable from `ugence_ai_hiring`:

| Name | Kind | Description |
| --- | --- | --- |
| `HiringPlatform` | class | The wired platform object returned by the composition root. |
| `build_in_memory_platform` | function | Composition root; returns a `HiringPlatform` wired with in-memory repositories and services. |
| `version_info()` | function | Returns a `VersionInfo` describing distribution and product metadata. |
| `VersionInfo` | type | Structured version/metadata record. |
| `PRODUCT_VERSION` | constant | Product (capability-maturity) version string. |
| `__version__` | constant | Distribution (wheel) version string. |

```python
from ugence_ai_hiring import (
    HiringPlatform,
    build_in_memory_platform,
    version_info,
    VersionInfo,
    PRODUCT_VERSION,
    __version__,
)
```

## `version_info()` fields

`version_info()` returns a `VersionInfo` exposing:

| Field | Meaning |
| --- | --- |
| `distribution` | Distribution (wheel) name, `ugence-ai-hiring`. |
| `distribution_version` | Packaging lifecycle version (e.g. `0.1.0`). |
| `product_version` | Capability-maturity version (e.g. `0.6.0`). |
| `platform_baseline` | Platform baseline the product targets. |
| `stability` | Stability marker for the distribution. |
| `release_classification` | e.g. `PACKAGE_READY_FOR_CONTROLLED_PILOT`. |
| `production_certified` | Always `False`. |
| `contract_versions` | Versions of the neutral governance contracts in use. |
| `dependency_versions` | Resolved versions of core Ugence dependencies. |
| `optional_integrations` | Optional extras present (e.g. `api`). |
| `build_commit` | Build provenance commit identifier. |

Distribution version and product version are **deliberately distinct**: the
distribution version tracks the packaging lifecycle; the product version tracks
H0–H6 capability maturity. See [VERSIONING.md](VERSIONING.md).

## CLI

```bash
python -m ugence_ai_hiring version   # distribution + product metadata (--json for JSON)
python -m ugence_ai_hiring verify    # assert safety/governance invariants; PASS/FAIL
python -m ugence_ai_hiring demo      # canonical offline safe demo
python -m ugence_ai_hiring report    # sample accountability report
```

Console script equivalent:

```bash
ugence-ai-hiring version
```

### Command notes

- `version` — prints distribution and product metadata; `--json` emits JSON.
- `verify` — asserts the package's safety/governance invariants and prints PASS/FAIL.
- `demo` — runs the canonical offline safe demo (evidence -> assessment ->
  advisory recommendation -> authorized human decision) and **stops before any
  enterprise action is executed**.
- `report` — prints a sample accountability report.
