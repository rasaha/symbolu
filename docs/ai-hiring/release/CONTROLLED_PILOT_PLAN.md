# Controlled Pilot — Plan

Scope and rules for the bounded controlled pilot of AI Hiring `0.6.0` (frozen at
`b9a0e3a`, `PACKAGE_READY_FOR_CONTROLLED_PILOT`).

> **The pilot validates operational behavior. It does not certify legal compliance,
> fairness, hiring quality, or production readiness.**

## Objectives

- Exercise the governed lifecycle end to end with **real human reviewers** making the
  binding decisions, under **persistent** infrastructure and **approved policies**.
- Confirm the accountability record (recommendation → TAP → human decision →
  ActionGate → simulated execution → reconciliation) is complete, reconstructable, and
  operationally useful in a realistic setting.
- Exercise operational procedures (startup, shutdown, rollback, incident, provider
  outage, reconstruction/audit verification) against durable storage.
- Collect evidence to inform a future go/no-go decision about production work — **not**
  to perform production hiring actions.

## Non-objectives (explicitly out of scope)

- No production external effects of any kind (see the entry checklist, §4).
- No legal/regulatory compliance certification.
- No fairness certification (fairness analysis remains read-only and descriptive).
- No hiring-quality or predictive-accuracy claim.
- No scale/performance benchmark.

## Parameters (to be fixed at entry)

| Parameter | Value (fill at entry) |
|---|---|
| Duration | e.g. 4–6 weeks (bounded, with a hard end date) |
| Participant count | small, named cohort of reviewers/approvers |
| Pilot cohort | the approved synthetic / de-identified case set |
| Data | synthetic **or** approved de-identified only |
| Environment | isolated pilot environment with durable audit storage |

## Included vs. excluded workflows

**Included:** requisition/candidate/application intake; evidence synthesis;
recommendation generation; TAP assertion evaluation; human review and decision;
action proposal; ActionGate authorization; **simulated** execution; reconciliation;
compensation/remediation; accountability reconstruction and reporting.

**Excluded / prohibited production actions:**
- Any real HRIS/ATS write.
- Any real candidate communication (email, message, calendar invite).
- Any offer issuance or rejection delivery (`ISSUE_OFFER` / `SEND_REJECTION` are
  unimplemented and must stay so).
- Any payroll or identity provisioning.
- Any egress of candidate data outside the pilot environment.

## Evaluation metrics (operational, descriptive)

- Lifecycle completeness: fraction of cases with a fully reconstructable chain
  (`integrity.reconstructed == True`).
- Governance-boundary adherence: zero AI-authored binding decisions; zero executions
  without authorization; zero silent mismatches (every mismatch → compensation
  required).
- Audit integrity: hash-chain valid, links intact, tenant scope consistent across all
  cases; tampering/broken links detected when injected in a drill.
- Operational: successful startup/shutdown/rollback drills; provider-outage handling;
  reconstruction/audit verification runs.
- Reviewer experience: qualitative feedback on the recommendation package and the
  accountability report (redacted).

These are **operational** measures. None is a fairness, compliance, or quality
certification.

## Success criteria

- Every reviewed case produces a complete, reconstructable, integrity-verified
  accountable record.
- No governance-boundary violation occurs (human-only decisions; no unauthorized
  execution; no silent success).
- All operational drills pass.
- No pilot-blocking or correctness defect remains open at exit (any found is documented
  and, if in the freeze exception list, fixed application-local).

## Stop criteria (halt the pilot)

- Any production external effect is observed or becomes possible.
- Any governance-boundary violation (an AI-authored binding decision; an execution
  without valid authorization; a silently-successful mismatch).
- Any audit-integrity failure that is **not** a deliberately injected drill.
- Any cross-tenant data exposure.
- Any unapproved PII entering the process.

## Escalation criteria

- Correctness or security defect → security owner + technical owner immediately;
  classify against the freeze exception list.
- Provider (TAP/ActionGate) outage beyond the documented tolerance → technical owner;
  follow the outage runbook.
- Reconstruction failure on real evidence → treat the affected record as untrusted;
  escalate to pilot owner.

## Exit

At the hard end date (or on a stop criterion), the pilot ends. Produce a pilot
evidence summary against the metrics and success criteria. Exit does **not** lift the
freeze (see [`FREEZE_DECLARATION.md`](FREEZE_DECLARATION.md)); a separate decision and
a new readiness assessment are required before any production work begins.
