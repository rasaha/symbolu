# Implementation Status — AI-Hiring Module

**Phase 1 — Foundation:** complete; 51 tests.
**Phase 2 — Evidence Ingestion & Normalization:** complete; 57 tests.
**Phase 2.5 — Evidence Boundary Hardening:** complete; 107 tests.
**Phase 3A — Capability Ontology & Rubric Contracts:** complete; 78 tests.
**Phase 3B — Deterministic Assessment Runtime:** complete; 65 tests.
**Phase 4A — DecisionCase Aggregate & Lifecycle:** complete; 55 tests.
**Total:** 413/413 module tests passing. No candidate evaluation, scoring
algorithm, evidence-derived recommendation generation, ranking, action execution,
CER construction, ActionGate invocation, or LLM inference has been introduced.
Phase 4A links assessments, advisory recommendations, and binding decisions as
distinct records and stops at `DECIDED`.

## Implemented

- [x] Isolated top-level `ai_hiring/` package (no changes to existing modules).
- [x] Domain enums: `ActorType`, `WorkflowState`, `Disposition`,
      `EvaluationStatus`, `ConfidenceLevel`, `CapabilityLayer` (ten fixed
      layers), `AuditEventType`.
- [x] Immutable, versioned domain contracts with validation:
      `NormalizedEvidence`, `LayerScore`, `CandidateEvaluation`,
      `Recommendation`, `Decision` (+ `Override`, `Approval`),
      `CandidateWorkflow`, `AuditEvent`, plus value objects
      `EvidenceRef`, `ReasonCode`, `Gap`, `Limitation`, `WeightedSummary`.
- [x] Contract rules: score ∈ [0,4]; ≥1 reason code per score; reason codes link
      evidence for score > 0; score 0 requires a gap or no-evidence reason;
      exactly ten unique capability layers per evaluation; non-binding
      `weighted_summary`; explicit `job_relevant`; immutability + revisioning.
- [x] Workflow state machine with typed transition errors and per-transition
      audit; guards centralized in `policies/transition_policy.py`.
- [x] Decision-boundary policy (`policies/decision_boundary.py`) with all
      required assertions and a pluggable `IdentityProvider`.
- [x] Separate `RecommendationService` (AI, advisory) and `DecisionService`
      (human, binding) — distinct types **and** services.
- [x] `WorkflowService`, `AuditService`, and a small `EvaluationService`
      (intake + explicit unblock).
- [x] Append-only audit with deterministic payload hashes, correlation/causation
      propagation, ordered entity history, and denial logging.
- [x] Repository ports + in-memory adapters: uniqueness, version-conflict
      detection, immutability, one-decision-per-evaluation, append-only audit.
- [x] Service-layer validation and boundary enforcement before persistence.
- [x] Callable API facade (`api/routes.HiringAPI`) with per-endpoint
      authorization hooks + pydantic request schemas; optional, lazily-imported
      FastAPI adapter.
- [x] Tests: domain validation, workflow transitions, recommendation/decision
      boundary, audit chain, and an end-to-end foundation scenario.
- [x] Documentation: `README.md`, `docs/ARCHITECTURE.md`, this file.

## Boundary invariants implemented (and tested)

1. `Recommendation` is always `actor_type = AI`; a non-AI actor is rejected.
2. `Decision` is always `actor_type = HUMAN`; **cannot be constructed** as AI.
3. Creating a decision requires an authenticated **human**; AI/service
   principals and unknown principals are rejected and audited.
4. AI actors cannot drive **any** workflow transition.
5. Binding transitions (`ADVANCED`/`HOLD`/`REJECTED`) require a valid human
   decision; a recommendation alone changes nothing.
6. Divergence from the AI recommendation requires a recorded `Override`.
7. A `REVIEW_BLOCKED` evaluation cannot enter review or be decided.
8. The full recommendation → decision → transition chain is reconstructable from
   the append-only audit log via correlation/causation ids.

## Not implemented (out of scope for Phase 1, by design)

- [ ] LLM calls / any model inference.
- [ ] Résumé parsing, evidence ingestion/normalization, indexing.
- [ ] Capability scoring, confidence prediction, gap generation.
- [ ] Candidate ranking / comparison.
- [ ] Assessment generation and delivery / candidate portal.
- [ ] Fairness, bias, disparity, standardization, drift analysis.
- [ ] Protected-attribute / prohibited-inference detection logic.
- [ ] ATS/HRIS and IAM/KMS integrations.
- [ ] Production database adapters.
- [ ] Frontend / review-console UI.

## Deferred (contract slots reserved; implementation later)

- [ ] `FairnessReport` — placeholder type only; the Consistency & Fairness
      Monitor is a later phase.
- [ ] Cryptographic audit hash-chain — `AuditEvent.previous_event_hash` is
      reserved so it can be added without a contract change.
- [ ] Real `IdentityProvider` (OIDC/SAML for humans, workload identity for
      services) — only `StaticIdentityProvider` (dev/test) exists now.
- [ ] Persistent, immutable audit backend and retention/versioning tooling.

## Known risks

- **In-memory only:** no durability; suitable for development and tests, not
  production. Concurrency is single-process (no locking model yet).
- **Audit `metadata` mutability:** `AuditEvent` is frozen, but its `metadata`
  mapping is a plain dict; the integrity guarantee is on `payload_hash`, not on
  post-hoc metadata edits. A future immutable-mapping type or hash-chain closes
  this.
- **Placeholder auth:** `StaticIdentityProvider` trusts its registry; real
  authentication is required before any non-test use.
- **Structural vs. semantic validation:** the domain enforces the *shape* of a
  score/evaluation, not its correctness — nothing here judges whether a score is
  *right* (that is later-phase scoring + validity work).
- No legal-compliance claims are made; only enforceable technical controls are
  described.

## Deviations from the original prompt structure

- Added `common.py` (stdlib helpers) and `errors.py` (typed error hierarchy) —
  supporting modules the prompt's structure implied but did not list.
- Added `services/evaluation_service.py` beyond the four named services, so
  evaluation intake and the explicit unblock action are not smuggled into route
  handlers or the workflow service. The four required services all exist.

---

# Phase 2 — Evidence Ingestion & Normalization

**Status:** complete; 57 Phase-2 tests + 51 Phase-1 tests green (108 total).

## Implemented

- [x] New `normalization/` package: `pipeline`, `parsers`, `cleaners`,
      `quarantine`, `hashing`, `provenance`, `chunking`, `lineage`, `models`.
- [x] New `index/` package: deterministic `interfaces`, `in_memory`, `search`.
- [x] New services: `EvidenceIngestionService`, `SearchService`,
      `ProvenanceService`.
- [x] New repositories: `evidence_artifacts` (provenance, chunk, quarantine,
      lineage) + `evidence_index_repository`; all in-memory, immutable.
- [x] Exact specified pipeline order, one audit event per stage.
- [x] Multi-format ingestion: TEXT, MARKDOWN, SOURCE_CODE, INTERVIEW_TRANSCRIPT,
      WORK_SAMPLE, PORTFOLIO_ARTIFACT, JSON, CSV, STRUCTURED_RESPONSE, DOCX
      (stdlib zip+XML), PDF (uncompressed text operators).
- [x] Immutable, versioned evidence with parent/ancestor linkage; no overwrite.
- [x] Full provenance (filename, uploader, timestamps, hashes, content length,
      source URI, version chain, transformation history) — never destroyed.
- [x] Deterministic SHA-256 `raw_hash` + `normalized_hash`; duplicate detection.
- [x] Profile-aware normalization (Unicode NFC, whitespace, line endings, tabs,
      repeated spaces, invalid-UTF repair, transport-artifact stripping) that
      preserves code/structured semantics.
- [x] Job-relevance + prohibited-field quarantine (configurable policy); values
      preserved separately, never exposed downstream, fully audited.
- [x] Exact-reconstruction chunking with offset/length/hash/type.
- [x] Deterministic search by candidate, role, assessment, evidence id, chunk
      id, assessment type, document type, filename, keyword, metadata.
- [x] Reconstructable evidence lineage DAG (parents/children/topological).
- [x] Phase-2 API endpoints on the callable facade + optional FastAPI adapter.
- [x] Docs: `docs/EVIDENCE_PIPELINE.md`.

## Additive touches to Phase-1 files (non-breaking)

- `domain/enums.py`: added Phase-2 `AuditEventType` members (existing members and
  values unchanged; all Phase-1 tests green).
- `errors.py`: added `IngestionError` family.
- `__init__.py`, `services/__init__.py`, `api/*`: additive wiring of the new
  repositories/services/endpoints. No Phase-1 domain invariant, workflow rule,
  decision-boundary check, audit semantic, or existing test was modified.

## Not implemented (out of scope for Phase 2, by design)

- [ ] Scoring, embeddings, LLM extraction, capability mapping, confidence,
      ranking, fairness, protected-attribute *inference*, ATS integrations,
      vector/semantic search, production database adapters, frontend.

## Known limitations

- **PDF**: only uncompressed text operators (no OCR / FlateDecode).
- **In-memory** repositories and index; single-process, non-durable.
- **Quarantine** classifies field *identity* (names/aliases), not free-text
  semantics — a prohibited attribute embedded in prose is not detected (that is
  later-phase inference work, deliberately excluded).
- **Audit `metadata`** mutability caveat from Phase 1 still applies.

---

# Phase 2.5 — Evidence Boundary Hardening

**Status:** complete; 107 Phase-2.5 tests + 108 prior tests green (215 total).
See `docs/EVIDENCE_BOUNDARY_HARDENING.md`.

## Implemented

- [x] Explicit extraction outcomes (`ExtractionStatus`/`ExtractionResult`);
      success never inferred from a returned string.
- [x] Fail-closed evaluation-eligibility policy with typed reason codes
      (`normalization/eligibility.py`) + `EvidenceValidationService`.
- [x] Configurable resource limits (`EvidenceLimits`) for input/text/archive/
      JSON/CSV.
- [x] DOCX/ZIP archive safety (bomb, ratio, traversal, absolute/deep path,
      encrypted entry, XML ceiling) — in-memory, no filesystem extraction.
- [x] JSON/CSV structured complexity limits; JSON duplicate-key rejection.
- [x] Text/source limits + binary-as-text rejection + deterministic invalid-UTF
      policy (replace + `SUCCEEDED_WITH_WARNINGS`).
- [x] PDF accurately represented as LIMITED (native-text only; encrypted →
      ENCRYPTED; empty → EMPTY blocked; ambiguous → MANUAL_REVIEW_REQUIRED).
- [x] Context-aware duplicate classification (`DuplicatePolicy`), incl.
      cross-tenant non-disclosure.
- [x] Lineage-integrity policy (no self-parent/cycle, parent existence, context
      match, monotonic version, conflicting predecessors) + typed errors.
- [x] Tenant/candidate/application scope on submissions, provenance, evidence,
      chunks, quarantine, index entries, lineage nodes.
- [x] Authorization-aware, tenant-scoped `EvidenceAccessService` +
      `EvidenceAccessPolicy` (permissions, grants, quarantine separate perm);
      denials audited; counts do not leak.
- [x] Quarantine non-leakage across normalized evidence/chunks/index/audit/
      errors; values only via quarantine permission.
- [x] Reconstruction integrity validator + hash checks (`hmac.compare_digest`).
- [x] Atomic (fail-closed) ingestion: validate before persist; no completed/
      indexed artifact on failure; deterministic retries; `IngestionState`.
- [x] Additive audit events; complete success/failure audit sequences.
- [x] Machine-readable format capability matrix + docs.

## Frozen files touched (additive only — exact reason)

- `domain/enums.py`: **added** Phase-2.5 `AuditEventType` members (safety audit
  events). No existing member/value changed.
- `domain/evidence.py`: **added** optional `tenant_id`/`application_id` to
  `NormalizedEvidence` with safe defaults (tenant isolation). No existing field
  changed; Phase-1 constructions remain valid.
- `errors.py`: **added** Phase-2.5 typed error classes.
- `normalization/models.py`, `normalization/parsers.py`,
  `normalization/pipeline.py`, `normalization/provenance.py`,
  `normalization/chunking.py`: **extended** additively for scope fields, limits,
  extraction status, and safety routing — Phase-2 behavior preserved (all
  Phase-2 tests green).
- `index/interfaces.py`, `index/search.py`: **added** optional `tenant_id`/
  `application_id` scope filters.
- `services/evidence_ingestion_service.py`: **reworked** to fail-closed/atomic
  while keeping the exact Phase-2 `evidence_id` 10-event success history
  (hardening events routed to a separate `ingestion_id` stream).
- `services/__init__.py`, `__init__.py`, `api/*`: additive wiring/endpoints.

## Known limitations

- PDF native-text only (no OCR/compressed/encrypted).
- In-memory repositories/index; atomicity simulated (no DB transaction).
- Quarantine classifies field identity, not free-text semantics.
- Placeholder authorization (grant store + Phase-1 identity provider).
- No cryptographic audit hash-chain yet.

---

# Phase 3A — Capability Ontology & Rubric Contracts

**Status:** complete; 78 Phase-3A tests + 215 prior tests green (293 total).
See `docs/CAPABILITY_ONTOLOGY.md`.

## Implemented

- [x] `ontology/`: immutable `Capability` + hierarchy (`CapabilityGraph`),
      evidence-type + reason-code vocabularies (`taxonomy`), versioning helpers.
- [x] `rubrics/`: `Rubric` contract, `RubricCapability` mapping, scoring scales,
      evidence-admissibility rules + missing-evidence semantics, uncertainty
      contracts, conflict representation, approval lifecycle.
- [x] `repositories/`: immutable versioned `ontology_repository`; append-only
      snapshot `rubric_repository`.
- [x] `services/`: `OntologyService` (publish/retire/supersede/lookup/list/
      history + hierarchy validation), `RubricValidationService` (deterministic
      contract checks), `RubricService` (Author→Reviewer→Approver→Publisher,
      segregation of duties, publish-requires-valid).
- [x] `api/`: `OntologyAPI` + `RubricAPI` callable facades with human-governance
      authorization hooks + optional FastAPI routers.
- [x] Additive `AuditEventType` members; every governance action audited.
- [x] Docs: `docs/CAPABILITY_ONTOLOGY.md` with Mermaid diagrams.

## Frozen files touched (additive only)

- `domain/enums.py`: added Phase-3A `AuditEventType` members.
- `errors.py`: added ontology/rubric typed error classes.
- `services/__init__.py`, `__init__.py`: additive wiring + `build_ontology_api`/
  `build_rubric_api`. No prior model, service, or test changed.

## Not implemented (explicitly out of scope)

- [ ] Candidate evaluation / scoring / ranking / recommendation.
- [ ] LLM inference, embeddings, prompt engineering, confidence prediction,
      fairness algorithms, ATS integrations.

## Known limitations

- In-memory repositories; placeholder human-governance authorization.
- Weight-total validation fixed at sum = 1.0 (tolerance 1e-6).
- No cryptographic signing of published contracts yet.

## Next milestone (from Phase 3A)

Phase 3B — Deterministic Assessment Runtime — is now implemented (see below).

---

# Phase 3B — Deterministic Assessment Runtime

Executes the immutable Phase-3A constitution deterministically, with **no AI
inference of any kind**. Phase 3B proves the evaluation constitution can execute
before any AI system is permitted to interpret evidence under it.

## Implemented

- [x] New `assessments/` package: `AssessmentWorkspace` + `CapabilityBinding`,
      `EvidenceBinding`, `ExcludedEvidenceRecord`, `MissingEvidenceRecord`,
      `Observation`, `CompletenessResult`, `CapabilityAssessment`, and the
      advisory-only `Assessment` (all frozen; `advisory_only: Literal[True]`).
- [x] Deterministic status vocabularies (`WorkspaceStatus`, `AssessmentStatus`,
      `CompletenessStatus`, `BindingProvenance`, `SupplierType`,
      `ObservationValidationStatus`); `PERMITTED_SUPPLIERS` excludes `AI_MODEL`.
- [x] `EvidenceBindingService`: fail-closed, criterion-specific binding under the
      Phase-3A `AdmissibilityPolicy`; declared evidence type from an authorized
      caller (never inferred); tenant/subject/quarantine/eligibility gates.
- [x] `AssessmentValidationService`: pure, deterministic observation validation —
      scale membership, declared-scale match, authorized non-AI supplier,
      evidence sufficiency, required uncertainty, permitted reason codes.
- [x] `AssessmentCompletenessService`: structural completeness only; HIGH/CRITICAL
      conflicts block finalization; never judges value quality.
- [x] `AssessmentService`: authorized, audited orchestration of create → bind →
      record-missing → observe → record-conflict → validate → finalize →
      supersede → cancel, plus reads.
- [x] `AssessmentWorkspaceRepository` + `AssessmentRepository` (append-only,
      versioned, supersession chains) + in-memory adapters.
- [x] `api/assessment_routes.py`: `AssessmentAPI` facade + optional FastAPI
      router. No score/rank/recommend/approve/reject/hire operation exists.
- [x] Additive `AuditEventType` members; every state change audited with the
      workspace correlation id.
- [x] Docs: `docs/DETERMINISTIC_ASSESSMENT_RUNTIME.md` with four Mermaid diagrams
      and the "No LLM inference in Phase 3B" label.
- [x] 65 new tests across 11 files; full module suite 358/358 green.

## Frozen files touched (additive only)

- `domain/enums.py`: added 13 Phase-3B `AuditEventType` members.
- `errors.py`: added the `AssessmentError` hierarchy (workspace/observation/
  authorization typed errors).
- `policies/evidence_access_policy.py`: added 8 assessment `Permission` members.
- `services/__init__.py`, `repositories/__init__.py`, `__init__.py`: additive
  exports + wiring + `build_assessment_api`. No prior model, service, or test
  changed; no existing contract semantics weakened.

## Not implemented (explicitly out of scope for Phase 3B, by design)

- [ ] Any LLM call, text interpretation, embedding, or similarity scoring.
- [ ] Scoring from free-form evidence, ranking, or candidate comparison.
- [ ] Recommendation generation, decisions, CER construction, ActionGate.
- [ ] Creating/modifying capabilities, rubrics, scales, or reason codes.
- [ ] Autonomous conflict resolution; mutating published contracts; the full
      DecisionCase aggregate.

## Known limitations

- In-memory repositories; placeholder grant-based authorization.
- Conflict *disposition* (resolving a HIGH/CRITICAL conflict) is deferred to a
  later authorized phase; the runtime only records and blocks on it.
- A criterion maps 1:1 to a capability (Phase-3A rubrics have no separate
  criterion concept); the contracts leave room for richer criteria later.

## Next milestone (from Phase 3B)

Phase 4A — DecisionCase Aggregate & Lifecycle — is now implemented (see below).
An interpretation-under-governance phase (earlier sketched as "Phase 3C") remains
future work and requires no contract changes to the runtime or the aggregate.

---

# Phase 4A — DecisionCase Aggregate & Lifecycle Orchestration

The governed case container linking evidence, assessments, recommendations, human
authority, and decisions as **distinct records with distinct authority**.

## Implemented

- [x] New `decision_cases/` package: immutable `DecisionCase` aggregate root
      (versioned, append-only snapshots), `RecommendationRecord` (advisory,
      `advisory_only: Literal[True]`), `DecisionRecord` (binding), `OverrideRecord`,
      `ReviewTask`, `AuthorityContext`, `SubjectRef`/`VersionedRef`, lifecycle
      transition table, and typed validation results.
- [x] Deterministic vocabularies (`CaseStatus`, `OperatingMode`, `ProposedOutcome`,
      `GeneratorType`, `RecommendationStatus`, `DecisionOutcome`, `AuthorityType`,
      `EffectiveStatus`, `ReviewTaskType`, `ReviewTaskStatus`). `AuthorityType` has
      no AI member.
- [x] `DecisionCaseService` (create/version/link/assign-review/complete-review/
      readiness/supersede/cancel/close), `CaseRecommendationService` (advisory
      submit/reject — never converts to a decision), `CaseDecisionService`
      (authority validation, binding decision, override — never executes),
      `CaseValidationService` (typed structural validation).
- [x] `InMemoryDecisionCaseRepository`: append-only case versions, immutable
      recommendations/decisions/overrides, append-only review-task revisions,
      supersession-chain retrieval.
- [x] `api/decision_case_routes.py`: `DecisionCaseAPI` facade + optional FastAPI
      router. **No** `execute_decision`/`send_to_actiongate`/`construct_cer`/
      `rank_candidates`/`auto_hire`/`auto_reject` endpoint exists.
- [x] Additive `AuditEventType` members (13); every material transition and denial
      audited with the case correlation id.
- [x] Docs: `docs/DECISION_CASE_AGGREGATE.md` with four Mermaid diagrams.
- [x] 55 new tests across 6 files; full module suite 413/413 green.

## Frozen files touched (additive only)

- `domain/enums.py`: added 13 Phase-4A `AuditEventType` members.
- `errors.py`: added the `DecisionCaseError` hierarchy (case/authority/readiness
  typed errors).
- `policies/evidence_access_policy.py`: added 11 case `Permission` members.
- `services/__init__.py`, `repositories/__init__.py`, `__init__.py`: additive
  exports + wiring + `build_decision_case_api`. No prior model, service, or test
  changed; no existing contract semantics weakened.

## Convention deviations from the prompt's file list

- Phase 1 already ships `services/recommendation_service.py` and
  `services/decision_service.py` (advisory `Recommendation` / binding `Decision`
  tied to `CandidateWorkflow`). To avoid overwriting them, the Phase-4A services
  are `case_recommendation_service.py` and `case_decision_service.py`, and the
  Phase-4A records are `RecommendationRecord` / `DecisionRecord` in
  `decision_cases/`. Nothing in Phase 1 was modified.

## Baseline note

- This module implements Phases 1, 2, 2.5, 3A, 3B, and 4A. The Phase-4A prompt
  assumed a "Phase 3C" interpretation layer; that layer is not present in the
  repository, so Phase 4A links the finalized advisory **Phase-3B** assessments
  directly. This is recorded here rather than silently assumed.

## Not implemented (explicitly out of scope for Phase 4A, by design)

- [ ] Enterprise action execution; production CER construction; ActionGate
      invocation; execution reconciliation; placeholder execution records.
- [ ] Generating recommendations from evidence; reinterpreting evidence; ranking
      or comparing candidates; replacing Phase 3B validation.
- [ ] AI as a binding decision authority.

## Known limitations

- In-memory repositories; placeholder grant-based authorization.
- Delegated-policy *bounds* are recorded and shape-validated (granting policy +
  scope/limits) but not yet evaluated against a live policy engine.
- Segregation of duties is enforced for the recommendation-author-vs-decider case;
  richer multi-approval quorums are left for a later phase.

## Next milestone

**Phase 4B — Action requests & CER binding** (future): bind a recorded decision to
a governed action request. Execution reconciliation is Phase 4C. Do not begin until
all Phase 1, 2, 2.5, 3A, 3B, and 4A tests pass.
