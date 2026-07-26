# H0 — Public API Migration & Re-entry Stabilization — Migration Report

Bounded stabilization phase completed against **Platform v1.0** (frozen). AI Hiring's
active/consumer code now imports governance concepts exclusively from the frozen
public API (`decision_governance.api`). **No platform behavior was changed, no new
hiring functionality was added, and no frozen platform file was modified.**

## 1. Objective & result

| Objective | Result |
|---|---|
| Active AI Hiring code consumes only `decision_governance.api` | **Done** — all 22 consumer files migrated; 0 remaining internal imports in consumer code |
| Preserve all behavior, contracts, schemas, tests | **Done** — 553/553 AI Hiring tests pass, unchanged |
| No modification to kernel / framework / TAP / ActionGate / any frozen package | **Done** — `git diff` touches only `ai_hiring/`, `domains/hiring/`, `applications/ai_hiring/` |
| No new hiring features | **Done** — imports only; zero logic changes |
| Remove in-scope technical debt (incl. TODO markers) | **Done** — see §5; no migration-scope TODOs existed |

## 2. Files changed (22)

Import-only edits (same symbols, identical objects — `decision_governance.api.X is
decision_governance.X`), no logic touched:

**Composition root (1)**
- `applications/ai_hiring/platform.py` — identity, audit, policy, repositories, ports (control-plane + external-execution consolidated into `api.ports`), services.

**Domain layer (2)**
- `domains/hiring/audit.py` — `api.audit` (incl. namespace predicates/catalogs)
- `domains/hiring/errors.py` — `api.errors`

**Application services (2)**
- `ai_hiring/services/evidence_access_service.py` — `api.identity`, `api.policy`
- `ai_hiring/services/assessment_service.py` — `api.identity`, `api.policy`

**API facades (6)**
- `ai_hiring/api/decision_case_routes.py` — `api.contracts`, `api.identity`, `api.services`
- `ai_hiring/api/action_request_routes.py` — `api.contracts`, `api.identity`, `api.services`
- `ai_hiring/api/execution_routes.py` — `api.contracts`, `api.identity`, `api.services`
- `ai_hiring/api/assessment_routes.py`, `rubric_routes.py`, `ontology_routes.py` — `api.identity`

**Domain models / adapters / policies / repositories (11)**
- `ai_hiring/domain/base.py` (`api.contracts`), `domain/audit.py` (`api.audit`), `domain/enums.py` (`api.identity`, `api.audit`)
- `ai_hiring/adapters/linked_records.py` (`api.ports`)
- `ai_hiring/policies/decision_boundary.py` (`api.identity`)
- `ai_hiring/repositories/interfaces.py`, `repositories/in_memory.py` (`api.repositories`)
- `ai_hiring/errors.py` (`api.errors`), `common.py` (`api.common`)
- `ai_hiring/rubrics/uncertainty.py`, `ontology/taxonomy.py` (`api.vocabulary`)

## 3. Internal imports removed → public API replacements

| Internal (removed) | Public API (added) | Symbols |
|---|---|---|
| `decision_governance.identity` / `.identity.actor` | `decision_governance.api.identity` | `IdentityProvider`, `StaticIdentityProvider`, `ActorIdentity`, `ActorType` |
| `decision_governance.policy` | `decision_governance.api.policy` | `EvidenceAccessPolicy`, `GrantStore`, `AccessRequest`, `Permission` |
| `decision_governance.audit` / `.audit.namespace` / `.audit.event(s)` / `.audit.repository` | `decision_governance.api.audit` / `.api.repositories` | `AuditService`, `AuditEvent`, `AuditEventType`, `AuditRepository`, `InMemoryAuditRepository`, `KERNEL_EVENTS`, `DOMAIN_EVENTS`, `LEGACY_EVENTS`, `is_kernel_event` |
| `decision_governance.repositories` | `decision_governance.api.repositories` | `InMemory{DecisionCase,ActionRequest,Execution}Repository` |
| `decision_governance.services` | `decision_governance.api.services` | 12 governance service classes |
| `decision_governance.decisions` / `.actions` / `.execution` (records & enums) | `decision_governance.api.contracts` | decision-case, action-request, execution records + enums |
| `decision_governance.actions` / `.execution` (ports) / `.ports.linked_record` | `decision_governance.api.ports` | `ActionControlPlanePort`, `OfflineDeterministicControlPlane`, `ExternalExecutionPort`, `OfflineDeterministicExecutionAdapter`, `LinkedRecordSnapshot`, `FINALIZED_STATUS`, `BLOCKED_METADATA_KEY` |
| `decision_governance.vocabulary` | `decision_governance.api.vocabulary` | `ReasonCode`, `ReasonCodeSpec`, `REASON_CODE_CATALOG`, `get_reason_code_spec`, `is_known_reason_code`, `UncertaintyLevel`, `UncertaintyRule` |
| `decision_governance.errors` | `decision_governance.api.errors` | full hiring error taxonomy (base + families) |
| `decision_governance.base` | `decision_governance.api.contracts` | `DomainModel` |
| `decision_governance.common` | `decision_governance.api.common` | `Clock`, `IdFactory`, `new_id`, `utc_now`, `canonical_hash` |

Object identity is preserved throughout (the public API re-exports the same objects),
so `isinstance`, hashing, and serialization are unchanged — verified by
`test_direct_kernel_adoption` (governed service/record types still resolve to
`decision_governance.*`).

## 4. Dependency cleanup

- `applications/ai_hiring/platform.py`: the two separate port imports
  (`decision_governance.actions` for the control plane, `decision_governance.execution`
  for external execution) were **consolidated into a single `decision_governance.api.ports`
  import** — the ports' true public home — removing the cross-import of action/execution
  record modules purely to reach the port classes.
- No other structural changes; no symbols added or removed from any hiring public surface.

## 5. TODO / debt resolution

A repository-wide scan of non-test hiring source found **no migration-scope TODO/FIXME/
stub markers**. The single `placeholder` marker
(`ai_hiring/api/routes.py:82`, "authorization hooks (placeholders for a real IdP)")
annotates a **fully-implemented** `_authorize` method and denotes future IdP integration
— an H3/H4 feature concern, explicitly out of H0 scope. It was intentionally left in place.

## 6. Compat shims — intentionally NOT migrated (see API Gap Report)

23 modules under `ai_hiring/` remain importing kernel internals **by design**. These are
backward-compatibility shims (pure `sys.modules` aliasing / full-surface re-export) whose
tested contract is to alias historical `ai_hiring.*` paths to the identical kernel modules
(`test_direct_kernel_adoption`). They are **not consumer code**; they mirror internals
(including non-public lifecycle tables the public API deliberately withholds) and cannot be
expressed through the flattened `api` without breaking tests or the frozen platform. Detail
and recommendation: `H0_API_GAP_REPORT.md`.

## 7. Validation summary

| Check | Result |
|---|---|
| AI Hiring test suite (`pytest ai_hiring`) | **553 passed** (unchanged from baseline) |
| Kernel + providers + hiring (`decision_governance governance_providers tap_provider actiongate_provider ai_hiring`) | **692 passed** |
| Platform Freeze verification (`python -m platform_freeze.verify`) | **PASS** — all 11 checks ok; core-tree hashes + API snapshots confirm frozen trees byte-identical |
| Dependency-direction verification | **PASS** — 0 violations; `applications.ai_hiring → domains.hiring → decision_governance` holds; platform never imports hiring |
| Frozen platform files modified | **None** — diff limited to `ai_hiring/`, `domains/hiring/`, `applications/ai_hiring/` |

**Pre-existing failure (not H0):** `platform_freeze/tests/test_freeze.py::test_classify_change_reports_evidence` fails on the clean tree with edits stashed. It is an artifact of the out-of-band `classify_change` self-test spanning post-freeze commits (returns `UNCLASSIFIED`); it does not touch the frozen platform or AI Hiring and is out of H0 scope.
