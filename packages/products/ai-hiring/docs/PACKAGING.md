# Packaging

`ugence-ai-hiring` is a pure-Python distribution. This document covers how to
build it, how to verify a built distribution, and what the artifacts contain.

## Build

```bash
python -m build packages/products/ai-hiring
```

This produces the wheel and sdist under the package's `dist/` directory:

- `ugence_ai_hiring-0.1.0-py3-none-any.whl`
- the matching sdist.

## Reproducibility

- The wheel is **bit-for-bit reproducible** (with `SOURCE_DATE_EPOCH` pinned).
- The sdist is **content-reproducible**.

Building twice with the same pinned inputs yields the same wheel bytes.

## Verify a distribution

A verification script is provided:

```bash
python scripts/verify_ai_hiring_distribution.py
```

Clean wheel, sdist, and editable installs are all verified, including imports and
the full test suite run from **outside** the repository.

## Wheel contents

The wheel ships:

- the canonical package `ugence_ai_hiring` (all source layers plus
  `platform.py`, `version.py`, `__main__.py`, `py.typed`), and
- the logic-free `ai_hiring` compatibility facade.

The wheel does **not** ship tests.

## Dependencies

Core hard dependencies:

- `pydantic>=2`
- `ugence-decision-authority>=1.0.0`
- `ugence-governance-provider-framework>=0.1.0`
- `ugence-governance-contracts>=0.1.0`

Optional extras:

- `api` = `fastapi>=0.100.0`, `uvicorn>=0.20.0`
- `dev` = `pytest`, `build`
- `all` = `fastapi`, `uvicorn`

The core deliberately excludes numpy, any AI/model SDK, any database driver, and
any web framework.

## Tests

The package contains 773 passing tests (749 migrated behavioral tests plus 24
new packaging/governance/dependency-boundary/import-isolation/compat/determinism
tests). The dev extra installs `pytest` and `build`.
