# Governance Provider Framework — Canonical-Package Migration Baseline

Exact pre-migration state, captured **directly from the live repository** (not
copied from the audit). Companion machine-readable data: `baseline_manifest.json`,
`test_manifest.txt`, `governance_providers.api.before.json`, `FILE_MAP.md`,
`PUBLIC_API_INVENTORY.md`, `IMPORT_GRAPH_BEFORE.md`, `ADAPTER_CLASSIFICATION.md`.

## 1. Repository state (verified directly)

| Item | Value |
|---|---|
| Default branch (remote `HEAD branch`) | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `ed7387f4` — *Merge pull request #1266* |
| PR #1266 integrated? | **Yes** — it is the default HEAD merge commit |
| Audit commits ancestors of default? | **Yes** — `c00385c9 … c9e8e77c` are in default history under #1266 |
| Migration branch | `claude/gpf-canonical-package-migration-y3qoew` (harness-designated; at default tip) |
| Starting commit | `ed7387f4576bf111c7f5544958dfb30bbe524906` |
| Working tree | clean |
| Python | 3.11.15 (Linux) |
| Dependency gaps at start | `pytest`, `pydantic`, `numpy` (pip-installed to run the baseline; **no repo file changed** to do so) |

**Branch-name note.** The prompt proposes a new branch
`claude/governance-provider-framework-canonical-package-migration`. The harness
mandates the feature branch `claude/gpf-canonical-package-migration-y3qoew` and
forbids pushing elsewhere. The harness branch is authoritative and is already
based on the latest integrated default tip (`ed7387f4`); it is used for all work.

## 2. Integrated components still present (verified)

- StoryGraph canonical package — `packages/capabilities/storygraph` / `ugence_storygraph` ✅ (316 tests)
- Governance Contracts canonical package — `packages/governance-contracts` / `ugence_governance_contracts` ✅ (45 tests)
- Decision Authority canonical package — `packages/capabilities/decision-authority` / `ugence_decision_authority`; `decision_governance` is an identity-preserving shim over it ✅ (79 tests)
- Terminology foundation — `scripts/validate_terminology.py` **PASS** ✅
- Governance Provider Framework — `governance_providers/` (not yet migrated) ✅ (42 tests)

## 3. Integrated baseline (all reproduced green; no NEW failures)

| Suite / check | Result |
|---|---|
| `python -m platform_freeze.verify` | **PASS** — substantive digest `477407149049968ed12eec71044a913dfc4dbbb8cf23327ea9eec5614d759bf0` |
| `scripts/validate_terminology.py` | **PASS** |
| `governance_providers/tests` | **42 passed** |
| `tap_provider` | **38 passed** |
| `actiongate_provider` | **30 passed** |
| `baseline_assertion_provider` + `baseline_action_provider` | **10 passed** |
| `packages/governance-contracts` | **45 passed** |
| `packages/capabilities/decision-authority` | **79 passed** |
| `packages/capabilities/storygraph` | **316 passed** |
| `ai_hiring` | **778 passed** |
| `enterprise_validation_pilot` | **164 passed** |
| `provider_heterogeneity_validation` | **51 passed** |
| `comparative_governance_benchmark` | **56 passed** |
| `platform_freeze/dependencies.dependency_report()` | **passed** (0 violations) |
| `platform_freeze/tests` | 19 passed, **2 PRE-EXISTING failures** (see §4) |

## 4. Pre-existing failures (recorded separately; NOT caused by this migration)

These fail on the clean starting tree (`ed7387f4`) before any change of mine, are
unit tests of the freeze *tooling* with stale assumptions from earlier phases, and
are **out of scope** to fix (§24 "do not fix unrelated repository defects"). The
freeze **verifier** (`platform_freeze.verify`) itself PASSES.

1. `platform_freeze/tests/test_freeze.py::test_classify_change_reports_evidence`
   — expects `proposed_classification ∈ {PATCH,MINOR,APPLICATION_LOCAL}` but the
   tooling now returns `UNCLASSIFIED` for an empty diff.
2. `platform_freeze/tests/test_freeze.py::test_hiring_baseline_discovery`
   — asserts `uses_provider_framework is False`, but a prior phase wired hiring to
   the provider framework, so discovery now reports `True`.

These must remain exactly 2 pre-existing failures after the migration (no
regression, no new failures introduced).

## 5. Framework facts (recollected directly, not assumed)

| Item | Value |
|---|---|
| Import package | `governance_providers` (one canonical source tree; **no** duplicate implementation) |
| `__version__` | `0.1.0` |
| `CONTRACT_VERSION` | `1.0.0` |
| Non-test modules / LOC | 29 / **1442** |
| Test files / LOC | 9 / **587** |
| Public API | `governance_providers.api` — **47 symbols** (`__all__`) |
| `core_tree_hashes[governance_providers]` | `ab12c0260bd9d49fdda37264aa1ad74e3b880bdc1b3bdfd303ae023e6c43cd2b` |
| `governance_providers.api` snapshot hash (computed) | `98dd02649e5fbb37879ef05e1b06afce1abd0cc10b5692b81974437d59f7a59b` |
| `governance_providers.api.json` file sha256 | `d4266914126b56baa0efc2dd73325a514248f17139b502e275993a95593b45a6` |
| Behavioural equivalence capture sha256 | `a8e3e7e9f47a9bb74ac794e8d2f89189ac49192745d02a311b1ea603045db4f5` |
| Frozen core tree? | **Yes** — one of four (`decision_governance`, `governance_providers`, `actiongate_provider`, `tap_provider`) |

## 6. Dependency shape (verified directly)

- **Pure core** (`registry`, `resolution.py`, `configuration.py`, `observability.py`,
  `fingerprint.py`, `version.py`, `conformance/*`, `reference/*`, and the
  `errors`/`lifecycle`/`metadata`/`contracts/*` re-export shims) imports **no**
  `decision_governance` — only stdlib, package-relative modules, and (in the shims)
  `ugence_governance_contracts`. `conformance/common.py` contains the *string*
  `"decision_governance"` inside an AST boundary check, not an import.
- **Only** the three `adapters/*` modules import `decision_governance.api`
  (public facade only). They contain **no** capability-specific (`tap`/`actiongate`)
  coupling — verified by grep. See `ADAPTER_CLASSIFICATION.md`.
- Importing `governance_providers` (top level) pulls only `.version` (+ the
  contracts bootstrap); it does **not** import `.api`/`.adapters`, so the top level
  is DA-free. Only `governance_providers.api` and `.adapters` transitively require
  `decision_governance` (the "adapters bleed").

## 7. Equivalence-capture harness

`scripts/gpf_equivalence_capture.py` deterministically fingerprints framework
behaviour through the **legacy** `governance_providers` surface (version predicates,
API symbol kinds, error MRO, registry registration + duplicate rejection,
per-kind deterministic resolution, reference-provider descriptors, fingerprint
determinism, lifecycle transition table). Run before and after; the two JSON dumps
must be byte-identical (gate GPF5). BEFORE sha256:
`a8e3e7e9f47a9bb74ac794e8d2f89189ac49192745d02a311b1ea603045db4f5`.

Baseline reproduced in full — **migration may proceed.**
