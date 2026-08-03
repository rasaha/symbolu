# Migration

Existing monorepo consumers should migrate from the legacy `domains.procurement`
and `applications.procurement` import paths to the canonical `ugence_procurement`
package. **Both keep working** — the migration is safe to do incrementally.

## Why migrate

- The canonical package is the single, supported implementation.
- The legacy paths are logic-free compatibility facades slated for eventual
  removal (see [COMPATIBILITY.md](COMPATIBILITY.md)).
- The curated `ugence_procurement.api` surface is frozen and stability-tested.

Because object identity is preserved, migrating changes only the import line — the
objects are identical, so behavior is unchanged.

## Before / after

Prefer the curated public API where possible.

```python
# Before (legacy paths — still work)
from applications.procurement.platform import build_in_memory_platform
from applications.procurement.api.routes import ProcurementAPI
from domains.procurement.requests.contracts import PurchaseRequest, PurchaseItem
from domains.procurement.policies.assessment import ProcurementAssessmentService
from domains.procurement.policies.budget_authority import BudgetAuthorityAdapter
```

```python
# After (canonical — recommended)
from ugence_procurement.api import (
    build_in_memory_platform,
    ProcurementAPI,
    PurchaseRequest,
    PurchaseItem,
    ProcurementAssessmentService,
    BudgetAuthorityAdapter,
)
```

Equivalently, the canonical modules may be imported directly (e.g.
`from ugence_procurement.platform import build_in_memory_platform`), but the frozen
`ugence_procurement.api` surface is the recommended entry point.

## Identity guarantee

```python
from domains.procurement.policies.budget_authority import BudgetAuthorityAdapter as L
from ugence_procurement.api import BudgetAuthorityAdapter as C
assert L is C   # same object — migration is a rename, not a rewrite
```

## Recommended steps

1. Replace `applications.procurement.*` and `domains.procurement.*` imports with `ugence_procurement.api` imports (or canonical module paths).
2. Run your existing tests — behavior is proven identical (`before == canonical == legacy`).
3. No configuration, wiring, or call-site changes are required.

## Scope

- The audit found **no** production or application consumers of the legacy paths
  outside the procurement test suite and two docs, so migration blast radius is
  negligible.
- New code should import canonical from day one.
