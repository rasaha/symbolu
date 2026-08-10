# Platform v1.0 — AI Hiring Integration Guide

How AI Hiring consumes the frozen platform. This is guidance for APPLICATION_LOCAL
work; it changes no frozen tree.

## Boundary (summary)

- **AI Hiring owns:** jobs, requisitions, candidates, applications, hiring evidence,
  interviews/work samples, hiring rubrics/assessments, candidate recommendations,
  hiring policies, offers/rejections, domain APIs/reports.
- **DGM owns:** decision cases, recommendation/decision records, human authority,
  review tasks, overrides, governed actions, execution intent, audit lifecycle,
  reconciliation.
- **TAP owns:** assertion/evidence evaluation, unsupported-component detection,
  qualifier preservation, provenance analysis, assertion constraints/obligations.
- **ActionGate owns:** authorization of proposed hiring actions, policy constraints,
  approval obligations, execution eligibility.
- **External systems own:** ATS mutation, email, calendar, offer-document generation,
  HRIS, background checks.

See `Project_documentation/ai_hiring/docs/ai-hiring/PLATFORM_BOUNDARY.md` for the authoritative table.

## Wiring pattern

1. Build the DGM services from `decision_governance.api` (cases, recommendation,
   decision, action, CER, authorization, execution, reconciliation).
2. Register providers through `governance_providers.api.ProviderRegistry`:
   TAP (assertion) and ActionGate (action). Resolve deterministically.
3. Use `AssertionAssessmentIntegration` to turn a TAP evaluation of a hiring claim
   into an assessment the recommendation cites — never an action authorization.
4. Use `ActionGovernanceControlPlaneAdapter` so ActionGate authorizes a proposed
   hiring action; enforce constraints before dispatch; verify obligations
   separately from execution success.
5. Keep the human/AI authority boundary: AI produces advisory recommendations only;
   an authenticated human creates the binding `Decision`.

## Non-negotiables

Respect F1–F20. Unsupported/indeterminate hiring assertions never advance as
supported; denied/indeterminate hiring actions never dispatch; provider failure is
fail-safe; no governance shopping across providers. New hiring capabilities are
APPLICATION_LOCAL and must not require a platform change.
