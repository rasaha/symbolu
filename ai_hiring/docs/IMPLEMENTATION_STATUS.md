# Implementation Status — AI-Hiring Module

**Phase 1 — Foundation:** complete; 51 tests.
**Phase 2 — Evidence Ingestion & Normalization:** complete; 57 tests.
**Total:** 108/108 module tests passing. No scoring logic exists anywhere.

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

## Next milestone

**Phase 3 — AI Evaluation Engine.** Consume the immutable evidence substrate
(extraction → rubric scoring → gaps → confidence → reason codes) behind the
Phase-1 human-decision boundary. Do not begin until all Phase 1 and Phase 2
tests remain green.
