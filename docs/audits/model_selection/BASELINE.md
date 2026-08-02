# Model Selection — Audit Baseline

Exact pre-audit state, captured **directly from the live repository** (not copied from prior reports).
Companion machine-readable data: `baseline_manifest.json`, `test_manifest.txt`, `FILE_MAP.md`,
`IMPORT_GRAPH.md`, `PUBLIC_API_AND_CONSUMER_MAP.md`.

This is an **audit-only** phase: no source moved, no canonical package created, no public API or
model-selection behavior changed, no routing policy or scoring formula altered, no Governance
Contracts / Hybrid LLM / AI Control Plane touched, no API snapshot or platform freeze re-baselined.

## 1. Repository state (verified directly)

| Item | Value |
|---|---|
| Default branch (remote `HEAD branch`) | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD | `66066e99` — *Merge pull request #1267* |
| PR #1267 integrated? | **Yes** — it is the default HEAD merge commit |
| GPF migration head & merge ancestors of default? | **Yes** — `db8875c0 … e7e3070e` present under #1267; merge `66066e99` is the tip |
| Earlier canonical migrations integrated? | **Yes** — Governance Contracts (#1261), StoryGraph (#1260/1262/1263), Decision Authority (#1264), Governance Provider Framework (#1266/#1267) |
| Audit branch | `claude/model-selection-audit-5hocjo` (harness-mandated; see note) |
| Starting commit | `66066e99fd187de017668303c94ff4164981840c` |
| Working tree | clean |
| Python | 3.11.15 (Linux) |
| Dependency gaps at start | `pytest`, `pydantic`, `numpy` (pip-installed to run the baseline; **no repo file changed**) |

**Branch-name note.** The prompt proposes `claude/model-selection-boundary-and-migration-readiness-audit`.
The execution environment mandates the feature branch `claude/model-selection-audit-5hocjo` and forbids
pushing elsewhere; per the prompt's own escape clause ("If the execution environment mandates a different
branch name, use the required branch and document the difference"), the mandated name is authoritative.
It is based on the verified default tip `66066e99`.

## 2. Completed components still present (verified)

- Governance Contracts — `packages/governance-contracts` / `ugence_governance_contracts` ✅ (45 tests)
- StoryGraph — `packages/capabilities/storygraph` / `ugence_storygraph` ✅ (316 tests)
- Decision Authority — `packages/capabilities/decision-authority` / `ugence_decision_authority` ✅ (79 tests)
- Governance Provider Framework — `packages/governance-provider-framework` / `ugence_governance_provider_framework` ✅ (84 tests)
- Terminology foundation — `scripts/validate_terminology.py` **PASS** ✅

All four canonical namespaces confirmed as `src/` package directories.

## 3. Integrated baseline (all reproduced green; no NEW failures)

| Suite / check | Result |
|---|---|
| `python -m platform_freeze.verify` | **PASS** — substantive digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6` |
| `scripts/validate_terminology.py` | **PASS** |
| `packages/governance-contracts` | **45 passed** |
| `packages/capabilities/storygraph` | **316 passed** |
| `packages/capabilities/decision-authority` | **79 passed** |
| `packages/governance-provider-framework` | **84 passed** |
| `tap_provider` | **38 passed** |
| `actiongate_provider` | **30 passed** |
| `platform_freeze.dependencies.dependency_report()` | **passed=True, 0 violations** |
| `platform_freeze/tests` | 19 passed, **2 PRE-EXISTING failures** (see §4) |
| Model Selection suites (`execution_gate`, `model_selection_experiment`, `model_selection_pilot`, `model_selection_reconciliation`, `execution_gate_shadow`) | **85 passed** |

Note: `governance_providers/tests` now collect **no tests** — the framework's tests were relocated to
`packages/governance-provider-framework` by PR #1267. This is expected, not a regression.

## 4. Pre-existing failures (recorded separately; NOT caused by this audit)

Identical to the failures documented in the GPF migration baseline; they fail on the clean starting tree
`66066e99` before any change, are unit tests of the freeze *tooling* with stale assumptions, and are out
of scope. The freeze **verifier** (`platform_freeze.verify`) itself PASSES.

1. `platform_freeze/tests/test_freeze.py::test_classify_change_reports_evidence` — tooling returns
   `UNCLASSIFIED` for an empty diff; test expects `PATCH/MINOR/APPLICATION_LOCAL`.
2. `platform_freeze/tests/test_freeze.py::test_hiring_baseline_discovery` — asserts
   `uses_provider_framework is False`; hiring was wired to the provider framework in an earlier phase.

These must remain exactly 2 pre-existing failures after the audit (this phase changes no code).

## 5. Model Selection footprint (facts, recollected directly)

| Item | Value |
|---|---|
| Capability | Two-stage policy: **ExecutionGate** (eligibility) + **ModelPolicy/route** (selection) |
| Primary source dirs | `execution_gate/`, `model_selection_experiment/`, `model_selection_pilot/`, `model_selection_reconciliation/` |
| Same-capability outside those | `governed_inference_pilot/adapters/{execution_gate,model_policy}.py` (a fifth live re-host) |
| Source LOC (non-frozen, 4 dirs) | ~**4,636** (execution_gate 1039 + experiment 1449 + pilot 1877 + reconciliation 271) |
| Test LOC (4 dirs) | ~**724** (196 + 200 + 201 + 127) |
| MS tests total | **85 collected, 85 passed** (+23 in `execution_gate_shadow`) |
| External imports of `execution_gate` | **none** (stdlib + self only) |
| In platform freeze? | **No** — not a core tree, no platform public-API snapshot |
| Local freeze | `execution_gate/frozen/replay_v1` — 13 artifacts, aggregate `8b05b2da798a6222`, verifier **PASS** |

## 6. Baseline reproduced in full

The integrated baseline reproduces green with exactly the two documented pre-existing freeze-tooling
failures and no new failures. **The audit may proceed.**
