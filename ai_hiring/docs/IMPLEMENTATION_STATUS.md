# Implementation Status — AI-Hiring Module

**Phase:** 1 — Foundation
**Status:** complete; 51/51 module tests passing.

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

## Next milestone

**Phase 2 — Evidence Ingestion & Normalization.** Produce `NormalizedEvidence`
from multi-format submissions, with the job-relevance quarantine and secure
indexing, behind the contracts and boundary established here. Do not begin AI
evaluation or fairness work until this foundation remains green.
