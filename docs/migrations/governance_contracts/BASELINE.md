# Governance Contracts Canonical-Package Migration — Baseline

Gate **C1**. Independently-verified pre-migration state. Machine-readable
companions: `baseline_manifest.json`, `baseline_freeze_hashes.json`,
`baseline_serialization.json`, `test_manifest.txt`.

## 1. Branch & commit

| Item | Value |
|---|---|
| Source branch | `claude/storygraph-canonical-package-migration-m25c2i` |
| Source commit at HEAD | `f076fa5b22e0e37395f5e59232dba690f208663c` |
| Implementation branch | `claude/governance-contracts-canonical-package-migration` |
| Working tree at start | **clean** (verified `git status --porcelain` empty) |
| Distribution / namespace | `ugence-governance-contracts` / `ugence_governance_contracts` |

## 2. Where the reusable contracts live today

The repository's neutral, reusable governance contracts are the **provider
framework contract core** under `governance_providers/`:

| Module | Symbols (neutral contracts) | Deps |
|---|---|---|
| `governance_providers/contracts/base.py` | `Provider` (Protocol), `BaseProvider` | `..lifecycle`, `..metadata` |
| `governance_providers/contracts/action.py` | `ActionGovernanceRequest/Result/Provider`, `ActionGovernanceOutcome` | `.base` |
| `governance_providers/contracts/assertion.py` | `AssertionGovernanceRequest/Result/Provider`, `AssertionCoverage` | `.base` |
| `governance_providers/contracts/execution.py` | `ExecutionDispatchRequest/Result`, `ExecutionObservation`, `ExternalExecutionProvider`, `ExecutionBusinessOutcome` | `.base` |
| `governance_providers/metadata.py` | `ProviderKind`, `ProviderCapabilities`, `ProviderCompatibility`, `ProviderDescriptor`, `ProviderHealth` | `.lifecycle` |
| `governance_providers/lifecycle.py` | `ProviderLifecycleState`, `is_legal_transition`, `assert_transition` | `.errors` |
| `governance_providers/errors.py` | `FailureClass`, `ProviderError` (+8 subclasses) | stdlib |

These modules import **only stdlib and each other** — no `decision_governance`,
no `pydantic`, no capability. They are a clean, pure, self-contained leaf. The
`governance_providers.contracts` closure is exactly `{errors, lifecycle,
metadata, contracts/base, contracts/{action,assertion,execution}}`.

**Framework (NOT contracts — stay in `governance_providers`):** `registry/`,
`resolution.py`, `conformance/`, `configuration.py`, `adapters/` (these import
`decision_governance` — the source of the transitive pydantic/DG drag),
`reference/`, `observability.py`, `fingerprint.py`, `api/`, `version.py`.

Other contract-like records considered and **NOT selected** (see §6):
kernel `ContextEnvelopeRecord`/`DecisionRecord`/`ActionAuthorizationResponse`
(`decision_governance/*` — capability-owned kernel records), CER v0_x records
(versioned-legacy), console-local ad-hoc CER (compatibility layer).

## 3. Baseline tests (independently re-run, all green)

| Package | Passed | Notes |
|---|---|---|
| `governance_providers` | **42** | primary package restructured |
| `decision_governance` | 29 | kernel |
| `tap_provider` | 38 | consumer |
| `actiongate_provider` | 30 | consumer |
| `baseline_action_provider` | 5 | consumer |
| `baseline_assertion_provider` | 5 | consumer |
| `enterprise_validation_pilot` | 164 | consumer |
| `comparative_governance_benchmark` | 56 | consumer |
| `provider_heterogeneity_validation` | 51 | consumer |
| `ugence_console_api` | 4 | consumer |
| `ai_hiring` | 778 | consumer |
| `platform_freeze` | 19 pass / **2 pre-existing fail** | see below |
| **Affected total passing** | **~1,221** | |

`governance_providers` deduplicated test-ID manifest: `test_manifest.txt` (42).

**Pre-existing platform_freeze failures (NOT caused by this phase):**
`test_classify_change_reports_evidence` returns `UNCLASSIFIED` because
`classify_change(FREEZE_COMMIT 5ae4f70, HEAD)` spans large unrelated repo
evolution; `test_hiring_baseline_discovery` expects `uses_provider_framework ==
False` but hiring now uses it. Both fail at the baseline commit before any change
here. The **manifest verification itself** (`test_stored_manifest_verifies`,
`test_full_verification_passes_and_is_reproducible`) is **green** — the frozen
`core_tree_hashes` and `public_api_manifests` currently match.

## 4. Frozen anchors (from `baseline_freeze_hashes.json`)

| Anchor | Value | Migration expectation |
|---|---|---|
| `governance_providers.api` snapshot hash | `98dd0264…f7a59b` | **MUST stay identical** — re-exports preserve symbol shape → proves C4 |
| `decision_governance.api` / `actiongate_provider.api` / `tap_provider.api` | (see file) | **unchanged** — those packages are not restructured |
| `governance_providers` core tree hash | `34bea183…c58c57a` | **WILL change** — modules become re-export shims → documented freeze re-baseline (plan §9) |

The API snapshotter records symbol *shape* (fields, enum values, signatures,
protocol methods) — **not** `__module__` — so moving a definition and re-exporting
it leaves the snapshot byte-identical.

## 5. Serialization fixtures (from `baseline_serialization.json`)

Representative instances of all 11 public dataclass contracts captured with
`asdict`, canonical JSON, fingerprint, `repr`, and constructor signature; all 6
public enums' value maps; and the 9 error classes' `failure_class`. These are the
C3/§12 equivalence anchors — every one must be byte-identical after the move.

## 6. Contract inventory & disposition (C1/§6)

| Contract | Path | Consumers | Neutral? | Authority meaning | Serialization stability | Disposition |
|---|---|---|---|---|---|---|
| Provider/BaseProvider | `governance_providers/contracts/base.py` | framework, all providers | Neutral | none (identity/lifecycle) | frozen | **SHARED_CANONICAL** |
| Action{Request,Result,Provider,Outcome} | `contracts/action.py` | actiongate_provider, benchmark, pilots, console | Neutral | authorization result | frozen | **SHARED_CANONICAL** |
| Assertion{Request,Result,Provider,Coverage} | `contracts/assertion.py` | tap_provider, benchmark, pilots, console | Neutral | advisory/evidentiary | frozen | **SHARED_CANONICAL** |
| Execution{Dispatch*,Observation,Provider,BusinessOutcome} | `contracts/execution.py` | pilots, ai_hiring | Neutral | external execution (transport/observed) | frozen | **SHARED_CANONICAL** |
| ProviderKind/Capabilities/Compatibility/Descriptor/Health | `metadata.py` | registry, all providers | Neutral | none (registration) | frozen | **SHARED_CANONICAL** |
| ProviderLifecycleState + transitions | `lifecycle.py` | base, registry | Neutral | none (availability) | frozen | **SHARED_CANONICAL** |
| FailureClass + ProviderError taxonomy | `errors.py` | framework, all providers | Neutral | none (error) | frozen | **SHARED_CANONICAL** |
| ProviderRegistry/Entry, resolution, SelectionRule | `registry/`, `resolution.py` | framework | Neutral-but-logic | none | frozen | **PLATFORM_OWNED** (framework — stays) |
| Adapters (→ kernel ports) | `adapters/` | framework | capability-coupled (imports DG) | none | frozen | **ADAPTER_OWNED** (stays) |
| Reference/baseline providers | `reference/`, `baseline_*` | tests | mock | none | — | **MOCK_OR_FIXTURE** (stays) |
| `ProviderInvocationRecord`, `fingerprint` | `observability.py`, `fingerprint.py` | framework | Neutral | none | frozen | **PLATFORM_OWNED** (framework observability — stays; re-imports contract errors) |
| Kernel `ContextEnvelopeRecord`, `DecisionRecord`, `ActionAuthorizationResponse` | `decision_governance/*` | kernel, ai_hiring | capability-owned | binding decision / CER | frozen | **CAPABILITY_OWNED** (stays with the kernel) |
| CER v0_1/2/3 records | `cer_v0_*/` | agent runtime | versioned | CER | — | **VERSIONED_LEGACY** (stays) |
| Console ad-hoc CER | `ugence_console_api/*` | console | duplicate | — | — | **LEGACY_COMPATIBILITY** (stays) |

**Boundary decision:** the `SHARED_CANONICAL` set = the pure closure `{errors,
lifecycle, metadata, contracts/base, contracts/{action,assertion,execution}}`.
This is a clean, well-bounded, stdlib-only leaf. The framework, adapters,
reference providers, kernel records, CER lines, and console copies **stay where
they are** — they are framework/capability/legacy, not shared neutral contracts.

## 7. Feasibility (why CONTINUE, not STOP)

- **Boundary is clear** (not `STOP — boundary unclear`).
- **Separation is safe** (not `STOP — cannot separate`): the neutral closure imports
  nothing capability-specific; a re-export shim at the old paths preserves every
  `governance_providers.*` import identically.
- **Freeze-legal:** `governance_providers` gaining `ugence_governance_contracts`
  as a leaf dependency is acyclic and not in `FORBIDDEN_IMPORTS` (F20 holds).
- **API snapshot preserved:** re-exports keep `governance_providers.api` shape →
  hash `98dd0264…` unchanged → C4 holds.
- **Only bookkeeping changes:** `core_tree_hashes[governance_providers]` changes;
  re-baselined and documented per plan §9 (a required report field, not a
  forbidden semantic change). No contract field/enum/serialization/digest changes.

## 8. Reproduction

```bash
git checkout claude/governance-contracts-canonical-package-migration   # @ f076fa5
pip install pydantic pytest
PYTHONPATH=. python -m pytest governance_providers/tests               # 42 passed
```
