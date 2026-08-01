# composite_threat_detector — COMPATIBILITY LAYER (moved)

> **This directory is a compatibility shim, not the implementation.**

The canonical StoryGraph capability moved to:

```
packages/capabilities/storygraph/            # canonical home
  src/ugence_storygraph/                      # canonical namespace
  tests/                                       # 289 tests
  docs/                                        # capability documentation
```

## What lives here now

- `composite_threat_detector/__init__.py` — a **logic-free redirect** that makes
  `import composite_threat_detector` and any `composite_threat_detector.<sub>`
  resolve to the **same** `ugence_storygraph` module objects (identity
  preserved). It exists only for the compatibility period.
- `conftest.py` — puts this directory on `sys.path` for legacy invocations.

## Migrate your imports

| Legacy (still works) | Canonical (use this) |
|---|---|
| `from composite_threat_detector import StoryGraph` | `from ugence_storygraph import StoryGraph` |
| `from composite_threat_detector.storygraph import ...` | `from ugence_storygraph.storygraph import ...` |
| — (curated small API) | `from ugence_storygraph.api import ...` |

**Removal / review target:** `ugence-storygraph` v3.0.0. See
`docs/migrations/storygraph/` and `packages/capabilities/storygraph/MIGRATION.md`.
