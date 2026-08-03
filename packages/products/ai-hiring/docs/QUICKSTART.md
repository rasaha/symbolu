# Quickstart

This walks through building an in-memory platform and running the offline demo.
Everything here runs deterministically and offline. No network access is used by
the core, and no downstream enterprise action is ever executed.

## Build an in-memory platform

`build_in_memory_platform()` is the composition root. It returns a
`HiringPlatform` wired with in-memory repositories and services.

```python
from ugence_ai_hiring import build_in_memory_platform

platform = build_in_memory_platform()
```

## Run the canonical demo

The demo shows the governed flow end to end:

> evidence -> assessment -> advisory recommendation -> authorized human decision

and then **stops before any enterprise action is executed**.

```bash
python -m ugence_ai_hiring demo
```

## CLI examples

```bash
# Distribution + product metadata
python -m ugence_ai_hiring version
python -m ugence_ai_hiring version --json

# Assert safety/governance invariants (prints PASS/FAIL)
python -m ugence_ai_hiring verify

# Run the offline safe demo
python -m ugence_ai_hiring demo

# Print a sample accountability report
python -m ugence_ai_hiring report
```

A console script is installed as well:

```bash
ugence-ai-hiring version
ugence-ai-hiring demo
```

## Inspect version metadata from Python

```python
from ugence_ai_hiring import version_info, PRODUCT_VERSION, __version__

info = version_info()
print(__version__)        # distribution (wheel) version
print(PRODUCT_VERSION)    # product (capability-maturity) version
```

See [API_REFERENCE.md](API_REFERENCE.md) for the full public API and the fields
returned by `version_info()`.
