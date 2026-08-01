# Governance Contracts Canonical-Package Migration — Report

**Verdict: `CONTINUE — governance-contracts canonical-package migration passed`.**

This phase establishes one canonical, independently packageable Ugence Governance
Contracts layer from the repository's existing neutral interfaces. It preserves
all current fields, enums, serialization, digests, authority meanings, and stable
import paths. Capability-owned records remain with their respective authorities,
known platform-contract gaps are documented for a later versioned evolution phase,
and no capability, product, orchestrator, or research implementation is redesigned.

---

## Branches & commits
| Item | Value |
|---|---|
| Source branch | `claude/storygraph-canonical-package-migration-m25c2i` |
| Target/implementation branch | `claude/governance-contracts-canonical-package-migration` |
| Starting commit | `f076fa5b22e0e37395f5e59232dba690f208663c` (working tree clean) |
| Ending commit | head of the implementation branch (see `git log`) |
| Commit sequence | baseline → relocate+shims+re-baseline → tests+packaging+verifier → docs+report |

## Test counts (baseline → final)
| Package | Baseline | Final |
|---|---|---|
| `governance_providers` | 42 | 42 |
| new `ugence_governance_contracts` package | — | **45** (compat/serialization/contract/leaf) |
| `decision_governance` | 29 | 29 |
| `tap_provider` | 38 | 38 |
| `actiongate_provider` | 30 | 30 |
| `baseline_action_provider` / `baseline_assertion_provider` | 5 / 5 | 5 / 5 |
| `enterprise_validation_pilot` | 164 | 164 |
| `comparative_governance_benchmark` | 56 | 56 |
| `provider_heterogeneity_validation` | 51 | 51 |
| `ugence_console_api` | 4 | 4 |
| `ai_hiring` | 778 | 778 |
| `platform_freeze` | 19 pass / 2 pre-existing fail | 19 pass / **same 2 pre-existing fail** |

Every consumer passes **unchanged**; +45 new tests. The 2 platform_freeze failures
are pre-existing and unrelated (documented in BASELINE §3).

## Affected package counts
- **Restructured (1):** `governance_providers` (contract modules → re-export shims).
- **New (1):** `ugence-governance-contracts`.
- **Consumers unchanged (11+):** all provider/kernel/pilot/console/hiring packages
  keep importing via `governance_providers` (compat path).
- **Packaging updated:** `dgm-provider-framework` pyproject + 4 isolation verifiers.

## Contracts moved (SHARED_CANONICAL)
`errors.py`, `lifecycle.py`, `metadata.py`, `contracts/{base,action,assertion,execution}.py`
— the pure, stdlib-only neutral closure. 31 public contract symbols + 2
framework-internal lifecycle mechanics.

## Contracts intentionally retained with their capabilities
Framework (`registry`, `resolution`, `conformance`, `configuration`, `adapters`,
`reference`, `observability`, `fingerprint`, `api`, `version`) stays in
`governance_providers`; kernel `ContextEnvelopeRecord`/`DecisionRecord`/
`ActionAuthorizationResponse` stay in `decision_governance`; CER v0_x stays;
console ad-hoc CER stays. See BASELINE §6 inventory.

## Legacy compatibility paths
`governance_providers.{errors,lifecycle,metadata,contracts,contracts.base,
contracts.action,contracts.assertion,contracts.execution}` and
`governance_providers.api` — all logic-free re-export shims resolving to the
**same objects**. Removal/review target: `governance_providers` 0.2.0.

## Public API before & after
- `governance_providers.api`: 48 symbols, snapshot hash `98dd0264…` — **unchanged**.
- New `ugence_governance_contracts.api`: 33 curated PUBLIC_STABLE symbols; full
  namespace `__all__` = 35. Full inventory: `PUBLIC_API_INVENTORY.md`.
- No public symbol removed; identity preserved across legacy↔canonical.

## Serialization comparisons
All 11 dataclass instances, 6 enum value-maps, and 9 error `failure_class` values
are **byte-identical** to `baseline_serialization.json` (asdict, canonical JSON,
fingerprint, repr, constructor signature). Pinned by
`tests/serialization/test_serialization_equivalence.py`.

## Digest comparisons (before → after, `baseline_freeze_hashes.json` → `after_freeze_hashes.json`)
| Hash | Before | After |
|---|---|---|
| `governance_providers.api` snapshot | `98dd0264…` | **SAME** |
| `decision_governance.api` / `actiongate_provider.api` / `tap_provider.api` snapshots | … | **SAME** |
| `governance_providers` core tree | `34bea183…` | **CHANGED** (extract+shims) |
| `decision_governance` / `actiongate_provider` / `tap_provider` core trees | … | **SAME** |

## Import graph before & after
- **Before:** `governance_providers/{contracts,errors,lifecycle,metadata}` defined
  the contracts (stdlib-only); framework/adapters imported them relatively;
  consumers imported `governance_providers.*`.
- **After:** `ugence_governance_contracts` (leaf, stdlib-only) defines them;
  `governance_providers` imports the leaf and re-exports; consumers unchanged.
  New edge `governance_providers → ugence_governance_contracts` is acyclic and
  not in `FORBIDDEN_IMPORTS` (F20 holds). The leaf imports nothing but stdlib+self
  (AST-verified, C5).

## Consumer migrations
Intentionally **kept on the compatibility path** (zero changes) — safest, and
avoids cascading frozen-tree re-baselines. All consumer suites pass unchanged.
New consumers should import `ugence_governance_contracts`.

## Wheel & clean-install results
- `ugence-governance-contracts` wheel builds; installs in a clean venv with
  `--no-index` (zero third-party deps); imports; round-trips.
- `dgm-provider-framework` four-wheel isolation (`verify_tap_provider_distribution.py`)
  passes end-to-end with the contracts wheel resolved as a dependency.

## Independent-distribution result
`verify_governance_contracts_distribution.py` — **PASS**: site-packages import, no
monorepo path, curated API + round-trip, and **no** unrelated Ugence package
importable in the isolated env.

## API snapshot changes
None. All four `platform/api-snapshots/*.json` are byte-identical.

## Freeze-manifest changes
`platform/PLATFORM_FREEZE_V1.json`: `core_tree_hashes[governance_providers]` and
`manifest_digest` re-baselined (2 lines) via `platform_freeze.write_manifest`.
`api_compatibility` classifies the change **PATCH**; `run_verification()` passes.
No other manifest field changed; api-snapshot files untouched. (Plan §9 re-baseline.)

## Contract gaps deferred
G1–G11 (tenant/environment identity, authority-type field, audit unification, CER
convergence, error envelope, idempotency, expiry/staleness, common result
envelope, correlation echo) — **documented, not implemented**. See
`CONTRACT_GAPS_AND_EVOLUTION_PLAN.md`.

## Known limitations
- Consumers remain on the compat path; a later phase may migrate them to the
  canonical import (each is a small, mechanical, per-package tree-hash re-baseline).
- The compat shims rely on `ugence_governance_contracts` being installed/importable
  (editable install in-repo; declared wheel dependency for the framework).
- No contract semantics evolved; all gaps deferred.

## Rollback procedure
`git revert` the migration commits in reverse (report → tests/packaging →
relocate+shims → baseline), or check out `f076fa5`. No data/evidence loss:
contract serializations are byte-identical from either layout; api-snapshots are
unchanged; the freeze re-baseline is a 2-line manifest change reproducible via
`write_manifest()`; the shim is independently removable at v0.2.0.

## Acceptance gates
| Gate | Status | Evidence |
|---|---|---|
| C1 exact baseline | ✅ | BASELINE.md, baseline_manifest.json, serialization/freeze hashes, test manifest |
| C2 one canonical shared package | ✅ | single source in `ugence_governance_contracts`; old paths are shims (no duplicate) |
| C3 no semantic change | ✅ | serialization + enum + error + api-snapshot byte-identical |
| C4 compatibility | ✅ | legacy↔canonical identity (45 tests); `governance_providers.api` hash unchanged |
| C5 leaf dependency | ✅ | AST scan: stdlib+self only; imports no capability/product/platform/console/research |
| C6 independent packaging | ✅ | wheel builds/installs `--no-index`/imports; verifier + TAP four-wheel isolation |
| C7 consumer integrity | ✅ | all consumer suites pass unchanged; framework wheel builds |
| C8 authority preservation | ✅ | no enum/effect/authority meaning changed; F4–F8/F16/F17/F20 hold |
| C9 gap separation | ✅ | G1–G11 documented, none implemented |
| C10 rollback safety | ✅ | git revert / checkout `f076fa5`; freeze reproducible; shim removable |

---

## Final verdict

**`CONTINUE — governance-contracts canonical-package migration passed`.**

This phase establishes one canonical, independently packageable Ugence Governance
Contracts layer from the repository's existing neutral interfaces. It preserves
all current fields, enums, serialization, digests, authority meanings, and stable
import paths. Capability-owned records remain with their respective authorities,
known platform-contract gaps are documented for a later versioned evolution phase,
and no capability, product, orchestrator, or research implementation is redesigned.
