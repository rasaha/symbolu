# Migration — `governance_providers` → `ugence_governance_provider_framework`

The capability-neutral Governance Provider Framework moved to the canonical
package `ugence_governance_provider_framework` (distribution
`ugence-governance-provider-framework`). The legacy `governance_providers`
namespace remains available and behaves identically.

## What changed

- **Canonical source:** `packages/governance-provider-framework/src/ugence_governance_provider_framework/`
  — one physical implementation (history-preserving `git mv`).
- **Legacy `governance_providers`** at the repository root is now a **logic-free
  compatibility shim** (a single `__init__.py`) that eagerly aliases the canonical
  submodules under the legacy dotted names, preserving object identity across the
  whole tree (top-level and deep imports).
- **Legacy `dgm-provider-framework` distribution** is now a **compatibility shell**
  depending on `ugence-governance-provider-framework[adapters]` (no duplicated source).
- **Decision Authority dependency is optional (boundary correction).** The three
  kernel-bound adapters load Decision Authority **lazily** (at invocation), so the
  framework core AND the canonical public API `...api` — including the adapter
  symbols — import without Decision Authority installed. Only *invoking* a
  kernel-bound adapter requires the `adapters` extra; without it, invocation raises
  a precise error naming `ugence-governance-provider-framework[adapters]`. With the
  extra installed, adapter behaviour is byte-for-byte identical. (This is stricter
  than the pre-migration `governance_providers.api`, which pulled the kernel at
  import; the correction is an import-boundary change only — no governance,
  authority, signature, field, enum, error, or serialization change, and the frozen
  API snapshot is byte-identical.)

## For consumers — nothing is required

Existing imports keep working unchanged and resolve to the **same objects**:

```python
from governance_providers.api import ProviderRegistry, resolve        # still works
from ugence_governance_provider_framework.api import ProviderRegistry, resolve  # canonical
# ProviderRegistry is the identical class object via both paths.

from governance_providers.contracts.action import ActionGovernanceOutcome  # deep import, still works
from governance_providers.reference import DeterministicAssertionProvider   # still works
from governance_providers.version import CONTRACT_VERSION                    # still works
```

New code should prefer the canonical namespace. The legacy namespace has no removal
date set in this phase; it will be reviewed alongside the `0.2.0` contract-shim
removal.

## Nothing else moved

Governance Contracts, Decision Authority, TAP, ActionGate, ACP, StoryGraph,
applications, domains, platform services, and concrete-provider authority are
**out of scope** for this migration and are unchanged.
