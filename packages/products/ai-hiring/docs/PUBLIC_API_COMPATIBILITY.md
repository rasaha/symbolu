# Public API Compatibility

The extraction into `ugence-ai-hiring` preserves the existing public semantics.
The new canonical API is a renamed home for the same objects, not a redesign.

## What is preserved

The canonical `ugence_ai_hiring` API preserves the existing semantics of the
original `ai_hiring` package. In particular, the following are **unchanged**:

- serialized field names,
- reason codes,
- workflow states, and
- audit event types.

Critically, **no `ai_hiring` string appears in serialized values**. Renaming the
import path did not leak into any serialized data, so previously produced records
remain consistent with new ones.

## Object identity

The `ai_hiring` compatibility facade re-exports objects from `ugence_ai_hiring`
with object identity preserved and deep submodule paths preserved:

```python
import ai_hiring
import ugence_ai_hiring

ai_hiring.build_in_memory_platform is ugence_ai_hiring.build_in_memory_platform
# True
```

## Baseline

A machine-readable baseline of the public API is captured in:

```
artifacts/public_api_baseline.json
```

This baseline records the public surface so that compatibility can be checked
against it.

## Migration

To move to the canonical import, rewrite `from ai_hiring import X` to
`from ugence_ai_hiring import X`. The old import keeps working through the
facade. See [MIGRATION_FROM_AI_HIRING.md](MIGRATION_FROM_AI_HIRING.md).
