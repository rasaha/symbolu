# AI Hiring ↔ Platform — Permanent Boundary

The permanent division of responsibility between AI Hiring (the application) and
the frozen Decision Governance Platform. AI Hiring depends on platform public APIs;
the platform never depends on AI Hiring. This boundary is authoritative for all
H1–H6 work.

## Ownership

| Concern | Owner |
|---|---|
| Jobs, requisitions, candidates, applications | **AI Hiring** |
| Hiring evidence, interviews, work samples | **AI Hiring** |
| Hiring rubrics, hiring assessments | **AI Hiring** |
| Candidate recommendations (content), hiring-specific policies | **AI Hiring** |
| Offers, rejections, domain APIs, domain reports | **AI Hiring** |
| Decision cases, recommendation records, decision records | **DGM** |
| Human authority, review tasks, overrides | **DGM** |
| Governed actions, execution intent, audit lifecycle, reconciliation | **DGM** |
| Assertion & evidence evaluation, unsupported-component detection | **TAP** |
| Qualifier preservation, provenance analysis, assertion constraints/obligations | **TAP** |
| Authorization of proposed hiring actions, policy constraints | **ActionGate** |
| Approval obligations, execution eligibility | **ActionGate** |
| ATS record mutation, email delivery, calendar scheduling | **External systems** |
| Offer-document generation, HRIS updates, background-check execution | **External systems** |

## Interaction rules

- AI Hiring produces a **hiring claim + evidence**; **TAP** evaluates whether the
  claim is supported and preserves qualifiers/provenance. The result becomes an
  **assessment** the DGM **recommendation** cites — never an action authorization.
- A hiring **recommendation** is advisory; only an **authenticated human** creates
  the binding DGM **decision** (F2/F3/F15).
- A proposed hiring **action** (e.g. issue offer) is authorized by **ActionGate**;
  constraints are enforced before dispatch; obligations are verified separately
  from execution success (F5/F13/F14).
- **External execution** (ATS/email/HRIS) is separate from authorization (F8) and is
  reconciled by DGM; providers never execute (F6).
- Unsupported/indeterminate hiring assertions never advance as supported;
  denied/indeterminate hiring actions never dispatch; provider failure is fail-safe;
  no governance shopping across providers (F9–F12, F19).

## What must never cross the boundary

- Hiring vocabulary/ontology must not leak into the platform (the kernel and
  providers stay domain-neutral).
- The platform must never import hiring packages.
- AI must never be recorded as human decision authority, in any hiring workflow.
