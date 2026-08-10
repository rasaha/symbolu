# H1 — Hiring Domain Completion — Completion Report

Application-local, additive completion of the candidate-facing hiring domain
surface on top of the frozen Platform v1.0. **No frozen platform file was
modified; no frozen API was changed; no workaround around the frozen architecture
was introduced.** All new code is under `ai_hiring/` and consumes the platform only
through `decision_governance.api`.

## Status

- **Implemented:** the H1 product entities, lifecycles, deterministic rules,
  repositories, application services, a hiring-owned domain audit trail, and
  reconstruction/audit support — with API-facing contracts.
- **Tests:** **41 new H1 tests**; full AI Hiring suite **594 passed** (was 553).
- **Frozen platform:** untouched — freeze verification **PASS**;
  dependency-direction **0 violations**.

## Audit-model decision (recorded)

H1's new product entities need lifecycle audit events, but the kernel
`AuditEventType` enum is frozen with no members for requisition / job-definition /
candidate / application events, and it must not be modified. Per the approved
decision, H1 uses a **hiring-owned domain audit trail**
(`ai_hiring/domain_audit/`) — a hiring-defined event taxonomy plus an append-only,
per-entity **hash-chained** event store. This is additive and boundary-correct
(AI Hiring owns its domain audit per `PLATFORM_BOUNDARY.md`); the kernel
`AuditService`/`AuditEventType` remain reserved for the governance chain (H3+).
Evidence-intake events are hiring-owned as well; no kernel event was reused
incorrectly.

## Implemented behavior

### Entities & contracts
| Entity | Module | Notes |
|---|---|---|
| `JobRequisition` | `ai_hiring/requisitions/requisition.py` | immutable+versioned; guarded lifecycle |
| `JobDefinition` | `ai_hiring/requisitions/job_definition.py` | binds requisition→rubric version; required capabilities/evidence; publish/retire |
| `Candidate` / `CandidateProfile` | `ai_hiring/candidates/candidate.py` | tenant-scoped identity; opaque `subject_id`; profile revisions; withdrawal |
| `Application` | `ai_hiring/hiring_applications/application.py` | links candidate↔requisition; structural lifecycle |
| `EvidenceIntakeItem` / `EvidenceProvenance` | `ai_hiring/intake/intake.py` | collected-evidence intake with provenance binding + content hash |

### Lifecycles (structural, deterministic, terminal-guarded)
- **Requisition:** DRAFT → OPEN ↔ ON_HOLD → FILLED/CLOSED/CANCELLED (terminal).
- **Job definition:** DRAFT → PUBLISHED → RETIRED (terminal).
- **Candidate:** ACTIVE → WITHDRAWN (terminal).
- **Application:** RECEIVED → SCREENING → ASSESSMENT → IN_REVIEW → CLOSED; WITHDRAWN
  from any active state. Terminal = CLOSED/WITHDRAWN. **No accept/reject/hire
  outcome** — binding decisions are deferred (see below).

### Deterministic rules
- **Eligibility** (`hiring_applications/eligibility.py`): requisition OPEN + in-tenant,
  job definition PUBLISHED + in-tenant + matching, candidate ACTIVE + in-tenant, no
  active duplicate — returns an explainable `EligibilityResult`.
- **Readiness** (`hiring_applications/readiness.py`): every `required_evidence_type`
  of the job definition is covered by collected intake — returns
  `ReadinessResult` with the exact missing types (incomplete evidence blocks
  ASSESSMENT).

### Repositories (`ai_hiring/repositories/product_repositories.py`)
Protocol ports + in-memory adapters for all five entities. Enforce unique
`(id, version)`, immutability (no overwrite → `VersionConflictError`),
latest-version reads, `history()` for reconstruction, active-duplicate detection,
and per-application evidence-type coverage.

### Application services (`ai_hiring/services/`)
`RequisitionService`, `CandidateService`, `ApplicationService`,
`EvidenceIntakeService` — each enforces tenant isolation (cross-tenant access is
denied and audited), validates lifecycle transitions, prevents duplicates, and
records domain audit events. `HiringReconstructionService` rebuilds any entity's
lifecycle from versioned history + the audit chain and verifies hash-chain
integrity and state-lineage consistency.

### Audit & reconstruction
- Hiring-owned, append-only, **hash-chained** domain audit events
  (`HiringDomainAuditEvent`); each event commits to its content and the previous
  event's hash — tamper-evident per entity.
- Every entity is immutable + versioned; reconstruction cross-checks the versioned
  state sequence against the audit `new_state` lineage.

### API-facing contracts (`ai_hiring/api/product_contracts.py`)
Dependency-light request DTOs (create/draft/register/submit/intake) and composite
view contracts (eligibility, readiness, reconstruction) — no web-framework
dependency.

## Completion criteria — evidence

| Criterion | Evidence |
|---|---|
| All H1 entities and lifecycle rules implemented | entities + status modules + rules above |
| Tenant and subject boundaries enforced | `ActorContext` + `guard_tenant`; cross-tenant denied+audited; candidate carries opaque `subject_id`, tenant-scoped (`test_h1_*` isolation tests) |
| Records deterministic, reconstructable, auditable | immutable+versioned records; hash-chained audit; `HiringReconstructionService` (`test_h1_reconstruction.py`) |
| No frozen platform files changed | `git diff` limited to `ai_hiring/` + `docs/`; freeze verification PASS |
| All existing 553 tests pass | full suite **594 passed** (553 + 41) |
| New tests cover valid flows, invalid transitions, duplicate prevention, access isolation, incomplete evidence, reconstruction | see coverage map below |
| Report separates implemented vs deferred | this document |

### Test coverage map (41 tests)
- **Valid flows:** requisition/job-def lifecycle, candidate register/revise/withdraw,
  application submit→…→close, intake+provenance.
- **Invalid transitions:** illegal requisition/job-def/candidate/application transitions;
  terminal states admit none.
- **Duplicate prevention:** active-duplicate application blocked; re-apply allowed after terminal; version-conflict immutability.
- **Access isolation:** cross-tenant denied + audited for requisition/candidate/application/intake/reconstruction.
- **Incomplete evidence:** readiness fails with exact missing types; ASSESSMENT blocked.
- **Reconstruction:** full-lifecycle rebuild; tamper detection; contiguous hash chain; tenant-scoped.
- **Boundary:** no hiring-decision outcome; no governance-decision contract touched; hiring events disjoint from frozen kernel enum; H1 imports only `decision_governance.api`.

## Explicitly deferred (H2–H6) — NOT implemented in H1

- **AI recommendation generation** and evidence→assertion synthesis — **H2 (TAP)**.
- **TAP integration** (assertion governance on hiring claims) — **H2/H3**.
- **ActionGate integration** (authorization of hiring actions) — **H3/H4**.
- **Offer execution / rejection execution** and external I/O — **H4**.
- **Fairness evaluation** and regulatory conclusions — **H5** (analysis only, caveated).
- **Binding hiring decisions** remain human-authored governance decisions — H1
  deliberately encodes no accept/reject/hire outcome and grants no actor decision
  authority.

## Validation summary

| Check | Result |
|---|---|
| AI Hiring suite (`pytest ai_hiring`) | **594 passed** (553 baseline + 41 H1) |
| Platform Freeze verification | **PASS** |
| Dependency-direction | **0 violations**; `applications.ai_hiring → domains.hiring → decision_governance.api` holds |
| Frozen platform files modified | **none** (diff = `ai_hiring/` + `docs/ai-hiring/`) |
| H1 code import surface | `decision_governance.api` only (`test_h1_boundary.py`) |

**Baseline limitations carried forward** (unchanged, pre-existing, not H1): the
`classify_change` freeze-tooling self-test failure and the whole-repository
`_SymboluFinder` collection errors in unrelated experimental modules. The H1 green
baseline is scoped to the platform-relevant packages, not the whole repository.
