# AI Hiring — Gap Analysis & Completion Roadmap (H1–H6)

Bounded roadmap to complete AI Hiring as a consuming application of the frozen
Platform v1.0. **Not executed in this phase.** The roadmap must not reopen the
platform architecture unless a real hiring workflow exposes a reproducible defect
(filed per `docs/platform-v1/MIGRATION_POLICY.md`).

## 1. Capability gap analysis

Status: IMPLEMENTED · PARTIAL (partially implemented) · SPEC (specified only) ·
MISSING · OUT (out of scope for the platform-consuming app).

| Capability | Status | Current artifact | Missing behavior | Platform dep | App-local | Phase |
|---|---|---|---|---|---|---|
| Job requisition | MISSING | — | requisition entity + lifecycle | DGM case (optional) | yes | H1 |
| Job definition | PARTIAL | rubrics/capability ontology | job→rubric binding contract | — | yes | H1 |
| Candidate | MISSING | — | candidate entity + identity | DGM subject ref | yes | H1 |
| Application | MISSING | — | application entity linking candidate↔job | DGM case | yes | H1 |
| Evidence collection | PARTIAL | evidence normalization + boundary | intake/ingest surface, sources | — | yes | H1 |
| Assessment workspace | PARTIAL | deterministic assessment runtime | reviewer workspace + structured observations | — | yes | H1 |
| Structured observations | PARTIAL | LayerScore/CandidateEvaluation | reviewer-entered observations model | — | yes | H1 |
| AI recommendation (generation) | MISSING | Recommendation *contract* only | evidence→assertion synthesis via TAP | **TAP** | yes | H2/H3 |
| Human review | IMPLEMENTED | decision boundary + review path | (migrate to review tasks) | DGM review tasks | yes | H3 |
| Decision | IMPLEMENTED | Decision (human-only) | — | DGM decision records | — | — |
| Override | PARTIAL | override contract | override workflow surfacing | DGM overrides | yes | H3 |
| Offer authorization | MISSING | action-request plumbing | authorize offer via ActionGate | **ActionGate** | yes | H4 |
| Offer execution | PARTIAL | execution/reconciliation runtime | offer-document + HRIS via external port | external systems | yes | H4 |
| Rejection communication | MISSING | — | rejection action + email via external port | external systems | yes | H4 |
| Candidate withdrawal | MISSING | — | withdrawal event + case closure path | DGM lifecycle | yes | H1/H4 |
| Case closure | PARTIAL | case lifecycle | hiring-specific terminal states | DGM lifecycle | yes | H1 |
| Audit reconstruction | PARTIAL | append-only audit + reconciliation | hiring audit-trail report | DGM audit | yes | H5 |

Nothing in this table requires a platform change; every dependency is satisfied by
the frozen public APIs.

## 2. Roadmap phases

Each phase: objective · permitted packages · frozen packages · required
functionality · safety invariants · test expectations · completion evidence ·
exclusions.

Phase list:

- **H0 — Public API Migration & Re-entry Stabilization** ✅ *complete*
- **H1 — Hiring Domain Completion** ✅ *complete*
- **H2 — AI Recommendation & Evidence Synthesis (TAP)** ✅ *complete*
- **H3 — Governance Integration (human decision on the DGM kernel)** ✅ *complete*
- H4 — Hiring Actions, Execution & Reconciliation
- H5 — Validation, Fairness Analysis & Shadow Pilot
- H6 — Packaging, Documentation & Product Wrap-up

### H0 — Public API Migration & Re-entry Stabilization  ✅ COMPLETE
- **Objective:** make AI Hiring a clean consumer of the frozen Platform v1.0 public API —
  replace every direct kernel-internal import in active/consumer code with
  `decision_governance.api`, without changing platform behavior or adding hiring features.
- **Permitted:** `ai_hiring`, `domains.hiring`, `applications.ai_hiring` (import surface only).
- **Frozen:** all platform trees; providers.
- **Delivered:** all active application/domain/service/adapter/repository/policy/API/
  composition-root code (22 files) migrated to `decision_governance.api`; two `platform.py`
  port imports consolidated into `api.ports`; 23 backward-compat shims left as an explicit,
  test-enforced exemption — **not** active application code (see `H0_API_GAP_REPORT.md`).
- **Invariants:** dependency direction (F20); object identity preserved.
- **Tests:** `pytest ai_hiring` → **553 passed** (unchanged); freeze verification **PASS**;
  dependency-direction **0 violations**; no frozen file modified. Green baseline is scoped to
  platform-relevant packages — two pre-existing, unrelated failures (`classify_change`
  freeze-tooling self-test; whole-repo `_SymboluFinder` collection errors) are carried forward
  as documented baseline limitations, so the whole repository is **not** claimed green.
- **Evidence:** `H0_MIGRATION_REPORT.md`, `H0_API_GAP_REPORT.md`, `H0_REENTRY_STATUS.md`.
- **Exclusions:** provider wiring; new features; any platform change.

### H1 — Hiring Domain Completion  ✅ COMPLETE
- **Objective:** complete the candidate-facing hiring product entities (requisition,
  job definition, candidate, application, evidence intake) with lifecycles, eligibility
  & readiness rules, repositories, application services, a hiring-owned domain audit
  trail, and reconstruction support.
- **Permitted:** `ai_hiring`, `domains.hiring`, `applications.ai_hiring` (app-local, additive).
- **Frozen:** all platform trees; providers.
- **Delivered:** entities + guarded lifecycles; deterministic eligibility/readiness;
  in-memory repositories (immutable, versioned, history); requisition/candidate/
  application/evidence-intake services with tenant isolation; hash-chained hiring-owned
  domain audit trail (`ai_hiring/domain_audit/`, per the audit-model decision below);
  `HiringReconstructionService`; API-facing request/view contracts.
- **Invariants:** F1–F3 (kernel owns governance records; AI advisory; **human-only
  binding decisions** — H1 encodes no accept/reject/hire outcome and grants no actor
  decision authority); dependency direction (F20).
- **Audit-model decision:** the frozen kernel `AuditEventType` has no members for the
  new product entities and must not be modified, so H1 uses a **hiring-owned domain
  audit trail** (additive, boundary-correct). See `H1_COMPLETION_REPORT.md`.
- **Tests:** **41 new H1 tests** — valid flows, invalid transitions, duplicate
  prevention, access isolation, incomplete evidence, reconstruction, boundary. Full
  suite **594 passed** (553 + 41).
- **Evidence:** `H1_COMPLETION_REPORT.md`; freeze verification PASS; 0 dependency
  violations; no platform diff.
- **Exclusions (deferred H2–H6):** AI recommendation generation; TAP/ActionGate
  integration; offer/rejection execution; fairness evaluation; binding decisions.

### H2 — AI Recommendation & Evidence Synthesis (TAP)  ✅ COMPLETE
- **Objective:** synthesize hiring evidence and generate an advisory, evidence-grounded
  recommendation package for human review, with every material claim evaluated through
  the **Assertion Governance Provider** (TAP).
- **Permitted:** `ai_hiring` + `governance_providers.api` (provider contract only).
- **Frozen:** kernel, framework, TAP, ActionGate contracts (untouched).
- **Delivered:** `EvidenceSynthesisService` (bounded, deterministic, provenance-
  preserving, minimization + protected-attribute controls); structured `HiringClaim`s;
  `ClaimAssertionEvaluator` via `AssertionAssessmentIntegration` (no TAP internals);
  advisory `HiringRecommendation` (statuses DRAFT / EVIDENCE_INCOMPLETE /
  ASSERTION_REVIEW_REQUIRED / READY_FOR_HUMAN_REVIEW / REJECTED_BY_REVIEW / SUPERSEDED —
  **no binding decision status**); replaceable `RecommendationGeneratorPort` +
  deterministic reference generator (no vendor SDKs in core); `RecommendationReviewPackage`
  + human-only reviewer dispositions; `RecommendationReconstructionService`; hiring-owned
  H2 audit events; API-facing contracts.
- **Invariants:** F2 (AI advisory; **human-only binding decisions** — reviewer actions
  human-only, no decide/execute path), F4/F6/F11/F12 (unsupported/indeterminate claims
  never review-ready; provider failure fail-safe; no governance shopping).
- **Tests:** **38 new H2 tests**; full suite **632 passed** (594 + 38); freeze PASS;
  0 dependency violations; no platform diff.
- **Evidence:** `H2_COMPLETION_REPORT.md`.
- **Exclusions (deferred H3–H6):** action authorization; ActionGate integration;
  offer/rejection execution; final hiring decisions; fairness certification; production
  model integrations.

### H3 — Governance Integration (human decision on the DGM kernel)  ✅ COMPLETE
- **Objective:** integrate the H1/H2 hiring domain with the frozen DGM kernel so every
  **eligible, review-ready** recommendation can be bound to a governed `DecisionCase` and
  resolved through an authorized **human** decision process — while remaining
  non-executable until H4. **No ActionGate wiring or execution.**
- **Permitted:** `ai_hiring` + `decision_governance.api` (kernel via public API only).
- **Frozen:** platform (kernel, framework, TAP, ActionGate) — untouched.
- **Delivered:** recommendation→DecisionCase binding (`GovernanceCaseBinding`); kernel
  recommendation submission (AI_ASSISTED, advisory); review-task lifecycle; **human**
  decisions via `CaseDecisionService` (human authority enforced by the kernel + H3 guard +
  access grants); acceptance/rejection; rationale + overrides; governance-case
  reconstruction with **cross-linked hiring↔DGM audit** (by correlation id); recommendation
  supersession; review workspace, governance dashboards, recommendation history; API contracts.
- **Invariants:** **Recommendation → Human Decision → (H4) Authorized Action** (never
  Recommendation → Action); F1–F3 (human-only binding decisions), F15, F18. Hiring audit
  events stay disjoint from the frozen kernel `AuditEventType`.
- **Tests:** **26 new H3 tests**; full suite **658 passed** (632 + 26); freeze PASS; 0
  dependency violations; no platform diff.
- **Evidence:** `H3_COMPLETION_REPORT.md`.
- **Exclusions (exclusively H4):** ActionGate authorization; external execution; offer/
  rejection execution; email/HRIS; compensation; execution reconciliation.

### H4 — Hiring Actions, Execution & Reconciliation
- **Objective:** authorize hiring actions (offer, rejection) via **ActionGate**,
  enforce constraints before dispatch, execute through an external port, reconcile.
- **Permitted:** app/domain + `actiongate_provider`, `governance_providers.api`,
  external adapters.
- **Frozen:** platform.
- **Required:** proposed hiring actions; ActionGate authorization; constraint
  enforcement; offer-document/HRIS/email via external execution port; reconciliation.
- **Invariants:** F5, F7–F10, F13, F14, F16, F17.
- **Tests:** denied/indeterminate offers never dispatch; constraints enforced;
  obligations verified separately; execution separate from authorization.
- **Exclusions:** live ATS/HRIS connectors; UI.

### H5 — Validation, Fairness Analysis & Shadow Pilot
- **Objective:** end-to-end hiring scenario validation + a bounded shadow pilot;
  audit-reconstruction reporting.
- **Permitted:** app/domain + validation harnesses (patterned on the pilot/benchmark).
- **Frozen:** platform.
- **Required:** hiring scenario matrix; safety-invariant checks; audit trail report.
- **Invariants:** all F1–F20 as applied to hiring.
- **Tests:** hiring-specific invariant suite; reproducible digest.
- **Exclusions:** **fairness conclusions** and regulatory claims (analysis only,
  clearly caveated); production deployment.

### H6 — Packaging, Documentation & Product Wrap-up
- **Objective:** package the hiring application independently; complete docs; close
  the workstream.
- **Permitted:** app/domain + packaging.
- **Frozen:** platform.
- **Required:** `dgm-ai-hiring` distribution(s) depending on frozen platform wheels;
  isolated-install verification; product docs; completion report.
- **Invariants:** dependency direction (F20); platform never imports hiring.
- **Tests:** packaging + isolated install; full suite green.
- **Exclusions:** public publishing; production certification.

## 3. Guardrails

- Run `python -m platform_freeze.classify_change` on every hiring change — it must
  classify as **APPLICATION_LOCAL** (or PATCH for docs/tests). Anything else means
  the change is touching the platform and must stop.
- Preserve all platform baseline tests; keep the four core trees byte-identical.
