# Governance Contracts Migration Guide

The neutral governance contracts moved from `governance_providers` into the
canonical leaf package `ugence_governance_contracts`. Full evidence:
`docs/migrations/governance_contracts/GOVERNANCE_CONTRACTS_CANONICAL_PACKAGE_MIGRATION_REPORT.md`.

## What changed

| | Before | After |
|---|---|---|
| Home | `governance_providers/{errors,lifecycle,metadata,contracts/*}` | `packages/governance-contracts/src/ugence_governance_contracts/` |
| Distribution | (part of `dgm-provider-framework`) | `ugence-governance-contracts` (own leaf wheel) |
| Namespace | `governance_providers.*` | `ugence_governance_contracts` |
| Curated API | `governance_providers.api` (framework + contracts) | `ugence_governance_contracts.api` (contracts only) |
| Deps | — | stdlib only (leaf) |

**No behavior changed.** `governance_providers.api`'s snapshot hash is unchanged;
every contract's fields/enums/serialization/digest is byte-identical.

## Update imports

```python
# Before                                              # After (preferred)
from governance_providers.api import ActionGovernanceRequest
from ugence_governance_contracts.api import ActionGovernanceRequest
```

Legacy `governance_providers.*` contract imports still work during the
compatibility period — they are logic-free shims resolving to the **same**
objects (identity preserved: `governance_providers.contracts.Provider is
ugence_governance_contracts.contracts.Provider`).

## Why re-export shims (not a symlink)

Shims preserve module identity across the boundary, so `isinstance` checks and
frozen protocol classes work whether imported by the legacy or canonical path. A
symlink would create a second top-level module name and a second, non-identical
class set. Each shim carries a compatibility docstring and a removal/review target
(`governance_providers` 0.2.0).

## Consumers

~70 consumer files import these contracts via `governance_providers`. They were
**intentionally left on the compatibility path** (zero changes): they keep passing
unchanged, and this avoids cascading tree-hash re-baselines across the frozen
provider/kernel/pilot packages. New consumers should import
`ugence_governance_contracts`.

## Freeze re-baseline

Extracting the closure changed `governance_providers`' source tree, so the
platform freeze manifest's `core_tree_hashes[governance_providers]` and
`manifest_digest` were re-baselined (2 lines in
`platform/PLATFORM_FREEZE_V1.json`). The four public API snapshots are unchanged;
`api_compatibility` classifies the change as **PATCH**.

## Rollback

`git revert` the migration commits in reverse, or check out the pre-migration
commit `f076fa5`. No data/evidence loss: contract semantics are byte-identical
from either layout, and the shim is independently removable at v0.2.0.
