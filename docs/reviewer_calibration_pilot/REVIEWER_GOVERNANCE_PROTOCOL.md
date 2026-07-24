# Reviewer Governance and Consent Protocol (Phase 2)

*How real reviewers are engaged, protected, and pseudonymized. This protocol binds whenever real
reviewers participate; in the absence of real reviewers it is dormant but complete.*

## Eligibility

A reviewer must have relevant technical, policy/risk/compliance, or operational expertise sufficient to
judge evidence obligations. No reviewer may participate who authored the frozen policy's rules or has a
stake in a particular outcome (see conflict of interest).

## Roles

- **Technical reviewer** — judges implementation/behavior/measurement claims.
- **Policy / risk / compliance / operational reviewer** — judges authority, actionability, and process.
- **Adjudicator (optional, independent)** — resolves disagreements; must not be one of the initial
  reviewers for the artifacts they adjudicate.

## Confidentiality

Reviewers access only permitted, de-identified/non-sensitive artifacts. Artifact contents and system
outputs are confidential to the pilot. Reviewers may not copy, export, or share artifacts.

## Conflict of interest

Each reviewer declares any conflict (authorship of the artifact under review, stake in the policy's
acceptance, reporting relationship to the pilot owner). Declared conflicts exclude the reviewer from the
affected artifacts.

## Consent

Reviewers consent, in writing, to: participation; logging of their decisions, timing, and confidence for
calibration purposes; pseudonymization of their identity; and the data-retention/deletion terms below.
Consent is informed and revocable.

## No employment use

Reviewer responses, timing, and agreement are used **only** for policy calibration. They are **never**
used for employment evaluation, performance review, or any personnel decision. This is a binding term.

## Withdrawal

A reviewer may withdraw at any time. On withdrawal, their in-progress reviews are discarded and their
personal data deleted; completed pseudonymized labels may be retained only if the reviewer consents,
otherwise deleted.

## Pseudonymization

Each reviewer is assigned a stable pseudonymous ID (e.g. `REV-A`, `REV-B`). Only the pseudonymous ID
appears in data, audit, and reports. The mapping from ID to identity is held separately, access-
controlled, and deleted at the retention horizon.

## Data retention and deletion

Reviewer decision/timing data is retained only for the calibration analysis window (bounded, stated at
pilot start) and then deleted. Reviewer identity mapping is deleted at or before that horizon. Deletion
is tenant-scoped and verifiable.

## Adjudicator independence

The adjudicator does not see the initial reviewers' identities and is not influenced by them beyond the
submitted labels. Adjudication decisions are recorded with rationale.

## Prohibited coaching

No one may coach reviewers toward the system's answers during outcome-bearing review. Training (Phase 4)
uses non-final artifacts only; the final set is never used to train or coach.

## Minimal data collection

Collect only what calibration requires: pseudonymous ID, role, expertise band, decisions, timing,
confidence, free-text reasons. Do not collect unnecessary personal information.
