# Backward Compatibility

The extraction preserves the legacy import paths `domains.procurement` and
`applications.procurement` so existing monorepo code keeps working unchanged.

## Mechanism: logic-free facades

The canonical implementation lives once, under
`packages/products/procurement/src/ugence_procurement/`. The monorepo
`domains/procurement/` and `applications/procurement/` trees are reduced to
**logic-free compatibility facades** that alias the canonical modules into
`sys.modules` under the legacy names. They contain no behavior of their own — they
re-export the identical canonical objects.

## Object identity preserved

The facades do not wrap, copy, or re-implement anything. A name imported through a
legacy path is the **same object** as the canonical name:

```python
from domains.procurement.policies.assessment import ProcurementAssessmentService as Legacy
from ugence_procurement.policies.assessment import ProcurementAssessmentService as Canon
assert Legacy is Canon   # identity, not just equality
```

There are not two physical implementations.

## Supported legacy import paths

| Legacy path | Resolves to |
|---|---|
| `domains.procurement.*` | canonical `ugence_procurement.*` domain modules |
| `applications.procurement.*` | canonical `ugence_procurement.*` application modules |

`namespaces = true` keeps `domains` / `applications` as PEP 420 namespace packages,
so this wheel never claims ownership of those unrelated package roots.

## Proven equivalence

A deterministic behavior capture recorded outcomes across the scenario matrix
against the original pre-extraction source, the canonical implementation, and the
legacy facades:

```
before    == canonical == legacy
541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
```

Behavior is preserved exactly. See [DETERMINISM.md](DETERMINISM.md).

## Classification and removal target

- **Compatibility classification: MINOR.** The legacy paths keep working via facades; no consumer must change today.
- The audit found **no** production or application consumers of the legacy paths outside the procurement test suite and two docs, so blast radius is negligible.
- The facades are a **transitional** convenience. New code should import from the canonical `ugence_procurement` (curated: `ugence_procurement.api`). The legacy paths are slated for removal in a future major cleanup once consumers have migrated (see [MIGRATION.md](MIGRATION.md)).
