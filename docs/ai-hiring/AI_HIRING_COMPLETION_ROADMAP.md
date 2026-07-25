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

### H1 — Hiring Domain Completion
- **Objective:** complete the hiring product entities (requisition, job definition,
  candidate, application, evidence intake, assessment workspace, structured
  observations, case-closure states) in `domains.hiring` / `applications.ai_hiring`.
- **Permitted:** `domains.hiring`, `applications.ai_hiring`, `ai_hiring`.
- **Frozen:** all platform trees; providers.
- **Required:** entity contracts + lifecycle; migrate consumer imports to
  `decision_governance.api`.
- **Invariants:** F1–F3 (kernel owns records; AI advisory; human-only decisions).
- **Tests:** entity validation, lifecycle, boundary; keep 553 green.
- **Evidence:** new hiring-domain tests; no platform diff.
- **Exclusions:** AI generation; provider wiring; external I/O.

### H2 — AI Recommendation & Evidence Synthesis
- **Objective:** synthesize hiring assertions from evidence and evaluate them with
  **TAP** (support, unsupported components, qualifiers, provenance).
- **Permitted:** app/domain + `tap_provider`, `governance_providers.api`.
- **Frozen:** kernel, framework, TAP, ActionGate contracts.
- **Required:** hiring-claim builder → `AssertionGovernanceRequest`; assessment via
  `AssertionAssessmentIntegration`; recommendation cites the assessment.
- **Invariants:** F4, F6, F11, F12; AI stays advisory (F2).
- **Tests:** unsupported/indeterminate hiring claims never advance as supported;
  provider failure fail-safe.
- **Exclusions:** action authorization; execution; fairness conclusions.

### H3 — Governance Integration
- **Objective:** run the full DGM case→recommendation→decision→review flow for
  hiring, with human authority and overrides through DGM review tasks.
- **Permitted:** app/domain + `decision_governance.api`, `governance_providers.api`.
- **Frozen:** platform.
- **Required:** review tasks, overrides, decision provenance; deterministic,
  auditable provider resolution for TAP.
- **Invariants:** F1–F3, F15, F18.
- **Tests:** human-only binding decisions; override audit; resolution determinism.
- **Exclusions:** offer/rejection execution.

### H4 — Hiring Action & Execution Workflows
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

### H5 — Validation, Fairness, and Shadow Pilot
- **Objective:** end-to-end hiring scenario validation + a bounded shadow pilot;
  audit-reconstruction reporting.
- **Permitted:** app/domain + validation harnesses (patterned on the pilot/benchmark).
- **Frozen:** platform.
- **Required:** hiring scenario matrix; safety-invariant checks; audit trail report.
- **Invariants:** all F1–F20 as applied to hiring.
- **Tests:** hiring-specific invariant suite; reproducible digest.
- **Exclusions:** **fairness conclusions** and regulatory claims (analysis only,
  clearly caveated); production deployment.

### H6 — Packaging, Documentation, and Product Wrap-up
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
