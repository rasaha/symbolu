# Reviewer Recruitment Plan (Phase 19)

*How real reviewers will be sourced for the internal pilot. No reviewer has been recruited in this track;
this is the plan the pilot administrator executes when the organization decides to run the human pilot.*

## Scope

Internal reviewers only. This pilot is an **internal** exercise: no external customer, no external
recruiting, no processing of prohibited or unapproved data. Recruiting an external customer is an explicit
stop condition (Phase 17).

## Roles and target counts

Five roles (Phase 2). Target a minimum roster that lets every final-set artifact reach
`REVIEWERS_PER_ARTIFACT` (2) independent reviewers plus a separated adjudicator:

| Role | Target | Why |
|---|---|---|
| Technical reviewer | ≥ 3 | code/impl/telemetry claims |
| Policy / risk reviewer | ≥ 2 | regulated, authority, risk-floor judgments |
| Domain reviewer | ≥ 2 | medical/financial/legal domain claims |
| Adjudicator | ≥ 1 | resolves disagreements; must not review the same artifact |
| Administrator | 1 | runs assignment, access, audit, retention |

A roster below the count needed to give every artifact two independent reviewers is reported as
**NOT ENOUGH ELIGIBLE REVIEWERS** — the assignment module records `unassigned` artifacts honestly rather
than faking coverage.

## Eligibility and exclusions

- Relevant expertise for the assigned role (Phase 3 eligibility).
- **Excluded:** anyone who authored the frozen policy's rules or has a stake in its acceptance; anyone
  with an unmanageable conflict of interest across too much of the set.
- Conflicts are declared at onboarding (COI template, Phase 3) and enforced by the assignment module.

## Sourcing

Draw from internal engineering, risk/compliance, and relevant domain teams. Reviewers participate
voluntarily; participation is never tied to employment evaluation (Phase 3, binding).

## Independence safeguards

- Reviewers are pseudonymous (`REV-A`, …) from first contact in the data path.
- No reviewer is coached toward the system's answers on final items; training uses non-final artifacts
  only (Phase 6).
- The adjudicator is recruited to be separable from the review pool for the artifacts they adjudicate.

## What recruitment does NOT establish

Recruiting and onboarding reviewers is apparatus readiness, not validation. Until real reviewers actually
review and the metrics run on real records, human validation remains **NOT EVALUATED** and no claim of
reviewer agreement or usability is made.
