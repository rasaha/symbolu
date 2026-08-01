# StoryGraph Migration Guide

StoryGraph moved from `cyber_security/composite_threat_detector/` to the
canonical Model-C layout `packages/capabilities/storygraph/`. This guide is for
consumers; the full evidence record is in
`docs/migrations/storygraph/STORYGRAPH_CANONICAL_PACKAGE_MIGRATION_REPORT.md`.

## What changed

| | Before | After |
|---|---|---|
| Distribution | (none — no wheel) | `ugence-storygraph` |
| Namespace | `composite_threat_detector` | `ugence_storygraph` |
| Home | `cyber_security/composite_threat_detector/` | `packages/capabilities/storygraph/` |
| Curated API | — | `ugence_storygraph.api` |
| Deps | stdlib only | stdlib only (unchanged) |

**No behavior changed.** Every frozen digest, version identifier, verdict, and
the full public API are identical (see the migration report).

## Update your imports

```python
# Before                                          # After (preferred)
from composite_threat_detector import StoryGraph  from ugence_storygraph import StoryGraph
from composite_threat_detector.storygraph import (…)   from ugence_storygraph.storygraph import (…)
#                                                  from ugence_storygraph.api import (…)   # curated
```

The legacy path still works during the compatibility period — it resolves to the
**same objects** via a logic-free redirect shim at
`cyber_security/composite_threat_detector/`. New code should use
`ugence_storygraph`.

## Compatibility mechanism (why not a symlink)

The legacy path is served by an explicit `importlib` meta-path **redirect
finder** (not a symlink and not a source copy). This was chosen over the repo's
packaging-symlink pattern because a redirect **preserves module identity**:
`composite_threat_detector.storygraph is ugence_storygraph.storygraph` is `True`,
so `isinstance` checks and singletons work across the boundary. A symlink would
create a second top-level module name and thus a second, non-identical set of
classes. The shim contains no business logic, declares itself
(`__compatibility__ = True`, `__canonical_package__`, `__removal_review_version__
= "3.0.0"`), and has its own contract tests.

## Removal timeline

The compatibility shim is scheduled for review/removal no earlier than
`ugence-storygraph` **v3.0.0**. Migrate imports before then.

## Contracts / product boundaries (unchanged this phase)

- StoryGraph continues to use its existing neutral request/result semantics. No
  tenant fields, authority enums, correlation, or evidence references were added
  or redesigned — that is deferred to the governance-contracts migration.
- No commercial *Ugence Sequence* product was created. A future product may
  compose StoryGraph + ActionGate + audit via StoryGraph's **public API**; this
  package is the reusable capability, not the product.

## Rollback

`git revert` the migration commits (baseline → final report) in reverse order,
or check out the pre-migration commit `6a49634` (tree identical to source commit
`c10f21f`). No data or evidence is lost: every moved file is a git-tracked
rename, historical evaluation records (`evaluation/prior_runs.py`, evidence
ledgers under `docs/`) are preserved verbatim, and all digests are reproducible
from either layout.
