# Changelog — AI Hiring product

All notable changes to the AI Hiring product. Versions follow the pre-1.0 policy in
[`VERSIONING.md`](VERSIONING.md): while on `0.x`, a MINOR bump may be
backwards-incompatible and a PATCH bump is additive/compatible. Nothing on the `0.x`
line is production-certified.

The product version tracks completed build phases (H0–H6 → `0.6.0`) and is distinct
from the repository's `symbolu` distribution version.

## [0.6.0] — H6: Packaging, Documentation & Product Wrap-up

**Added**
- `ai_hiring.product` — curated public API surface (composition, config, demo,
  accountability, version).
- Typed, **fail-closed** configuration (`ProductConfig`, `load_config`,
  `ExecutionMode`): unknown keys, invalid values, and production execution modes all
  fail closed.
- Deterministic composition roots: `build_dev_platform`, `build_demo_platform`.
- Safe canonical demo (`run_demo`, `canonical_cohort`) — five synthetic cases across
  the governed branches, in-memory and reproducible.
- Human- and machine-readable **accountability report**
  (`build_accountability_report`) with deterministic PII redaction.
- CLI: `python -m ai_hiring.product {version|demo|report|verify}`.
- Full product documentation set (install, quickstart, config/API references,
  architecture + diagram, deployment, operations runbook, security review,
  dependency review, packaging, versioning, known limitations, product-claims audit).
- H6 test suite (product behavior + packaging boundary).

**Changed**
- Documentation wording: deterministic providers are described as *"deterministic
  provider implementations used only for validation"* rather than "reference
  providers", to avoid implying a production-recommended implementation.

**Unchanged (by design)**
- No new governance/decision/authorization/execution semantics.
- No frozen platform file modified (freeze verification PASS; 0 dependency violations).

## [0.5.0] — H5: Validation, Fairness Analysis & Bounded Shadow Pilot
- End-to-end scenario matrix, bounded synthetic shadow pilot, read-only fairness
  analysis, reconstruction verification, audit completeness, failure injection, local
  performance characterization. Readiness: `READY_WITH_DOCUMENTED_LIMITATIONS`.

## [0.4.0] — H4: Action Authorization, Execution & Reconciliation
- ActionGate authorization, external execution via a deterministic adapter, receipts,
  reconciliation, and compensation/remediation — transport separated from outcome.

## [0.3.0] — H3: Governance Integration & Human Decisions
- DGM DecisionCase binding and authorized human decisions for eligible, review-ready
  recommendations; override recording on divergence.

## [0.2.0] — H2: Recommendations, Evidence Synthesis & TAP
- Evidence-grounded recommendation packages whose material claims are evaluated
  through the Assertion Governance Provider (TAP) before human review.

## [0.1.0] — H0–H1: API Migration & Hiring Domain Foundation
- Public-API migration and re-entry stabilization; hiring domain (requisitions,
  candidates, applications, evidence intake) with a hiring-owned hash-chained domain
  audit disjoint from the kernel audit enum.
