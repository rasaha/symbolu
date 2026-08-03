# Migration from `ai_hiring`

The package's canonical import name is now `ugence_ai_hiring`. The old
`ai_hiring` import continues to work through a compatibility facade.

## Preferred: update your imports

```python
# Before
from ai_hiring import build_in_memory_platform

# After
from ugence_ai_hiring import build_in_memory_platform
```

The general rewrite is:

```python
from ai_hiring import X        # old
from ugence_ai_hiring import X # new
```

## The facade preserves old imports

The wheel ships a logic-free `ai_hiring` compatibility facade that re-exports the
same objects from `ugence_ai_hiring`. This means:

- `import ai_hiring` continues to work.
- Deep submodule paths are preserved.
- **Object identity is preserved** — an object reached via `ai_hiring` is the
  same object as the one reached via `ugence_ai_hiring`:

```python
import ai_hiring
import ugence_ai_hiring

ai_hiring.build_in_memory_platform is ugence_ai_hiring.build_in_memory_platform
# True
```

No behavior changes when you keep the old import; you simply route through the
facade.

## Monorepo note

Inside the monorepo, the **original historical `ai_hiring/` source tree is
retained unchanged**. Converting the in-repo tree to the facade form is deferred
to a later cleanup PR in order to preserve the platform freeze. The logic-free
facade takes effect for **clean installs of the independent wheel**.

## Serialized values are unchanged

Migrating imports does not change any serialized data. Serialized field names,
reason codes, workflow states, and audit event types are unchanged, and no
`ai_hiring` string appears in serialized values. See
[PUBLIC_API_COMPATIBILITY.md](PUBLIC_API_COMPATIBILITY.md).
