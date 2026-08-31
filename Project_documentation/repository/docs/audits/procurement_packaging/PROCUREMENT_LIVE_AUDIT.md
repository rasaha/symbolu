# Procurement Packaging — Phase-Zero Live Audit

Live audit of the procurement reference domain performed immediately before the
independent-package extraction. All numbers are the observed live values, not
historical assumptions.

## Live starting point

| Field | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default tip (recorded) | `b760c9e5440bc4572c9f3a197a682b0c95b53ad8` |
| Working branch | `claude/procurement-independent-package-yypnqs` |
| PR #1299 (ActionGate migration) | merged (ancestor of the recorded tip) |
| PR #1301 (AI Hiring canonical providers) | merged; the recorded tip is its merge commit |
| Python | 3.11.15 |
| pydantic | 2.13.4 |
| Baseline procurement tests | **33 passed** (`domains/procurement/tests/`) |

No newer *procurement*-specific branch or open PR was found; the extraction starts
from the current clean default tip. The AI Hiring independent package
(`packages/products/ai-hiring`, distribution `ugence-ai-hiring`) is the established
standalone-product pattern this extraction mirrors.

## Source inventory (`SOURCE_INVENTORY.json`)

32 Python files under `domains/procurement/` and `applications/procurement/`:
**24 non-test** implementation/metadata files + **8 test** files. Each is recorded
with its git blob SHA and SHA-256 in `SOURCE_INVENTORY.json`. Classification:

| Class | Files |
|---|---|
| DOMAIN_CONTRACT | `requests/contracts.py`, `errors.py`, `approvals/mappings.py`, `actions/mappings.py`, `suppliers/outcomes.py` |
| VALIDATION | `validation/request_validation.py` |
| POLICY | `policies/assessment.py`, `policies/budget_authority.py`, `policies/policy_adapter.py` |
| ADAPTER | `suppliers/adapter.py`, `adapters/linked_records.py` |
| CONFIGURATION | `applications/procurement/configuration.py` |
| APPLICATION_COMPOSITION | `applications/procurement/platform.py` |
| API_FACADE | `applications/procurement/api/routes.py` |
| PACKAGE_METADATA | the `__init__.py` files |
| TEST | `domains/procurement/tests/*` (8 files, 33 tests) |

## Consumer inventory (`CONSUMER_MAP.json`)

A whole-repository search for `domains.procurement`, `applications.procurement`,
`ProcurementPlatform`, `ProcurementAPI`, `build_in_memory_platform`,
`BudgetAuthorityAdapter`, `SupplierExecutionAdapter`, and
`ProcurementAssessmentService` found **no production or application consumers**
outside the procurement packages themselves. The only consumers are:

* the procurement test suite (`domains/procurement/tests/*`, TEST); one of these
  (`test_cross_domain_conformance.py`) additionally imports `applications.ai_hiring`;
* two documentation files (`docs/PROCUREMENT_REFERENCE_DOMAIN.md`,
  `docs/DGM_PLATFORM.md`).

This clean consumer graph is why the legacy trees can be converted to logic-free
facades with negligible blast radius.

## Dependency inventory (`IMPORT_GRAPH_BEFORE.json`, `DEPENDENCY_CLASSIFICATION.md`)

The only non-stdlib import roots in the original implementation are
**`decision_governance`** (the legacy DGM kernel namespace) and **`pydantic`**.
No NumPy, FastAPI, database driver, web client, cloud SDK, model SDK, TAP,
ActionGate, governance-provider-framework, or governance-contracts import exists in
the procurement source. See `DEPENDENCY_CLASSIFICATION.md`.

`decision_governance` is itself already a **compatibility-only** facade over the
canonical `ugence_decision_authority` distribution, so the canonical dependency
migration is a pure import-path rewrite (`decision_governance.api.* →
ugence_decision_authority.api.*`) with no behavior change.

## Behavior baseline (`artifacts/BEHAVIOR_CAPTURE_BEFORE.json`)

A deterministic behavior capture (`scripts/capture_behavior.py`) records
representative outcomes across the §4.4 scenario matrix — assessments (valid,
budget-insufficient), validation error taxonomy, action mappings, happy-path
end-to-end run, above-threshold constrained authorization, restricted-supplier and
hard-limit fail-closed denials, supplier outcome vocabulary, and the audit-event
sequence — with all volatile ids/timestamps masked.

Captured against the original pre-extraction source (in a git worktree at
`b760c9e5`), the canonical `ugence_procurement` implementation, and the legacy
facades:

```
before    : 541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
canonical : 541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
legacy    : 541a5ab70af18e774e00cfc99986f87f96db7ccb2424478c20362527988a4336
```

**`before == canonical == legacy`** — behavior is preserved exactly.

## Duplication disposition (`DUPLICATION_DISPOSITION.md`)

The canonical implementation lives once, under
`packages/products/procurement/src/ugence_procurement/`. The monorepo
`domains/procurement/` and `applications/procurement/` trees are reduced to
logic-free compatibility facades that alias the canonical modules into
`sys.modules` under the legacy names (object identity preserved). There are **not**
two physical implementations.
