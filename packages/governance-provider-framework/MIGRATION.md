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
- **Decision Authority dependency is optional.** The core (`registry`, `resolution`,
  `configuration`, `observability`, `fingerprint`, `version`, `conformance`,
  `reference`, contract shims) installs and imports without Decision Authority. The
  kernel-bound `adapters` and the `.api` aggregator need the `adapters` extra —
  identical to the pre-migration behaviour where importing `governance_providers.api`
  pulled the kernel.

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
