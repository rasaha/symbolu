# Reviewer Governance Protocol (Phase 3)

*Templates and rules for engaging real reviewers later. No real reviewer data is collected in this track;
these are the forms and rules the pilot administrator applies at onboarding.*

## Eligibility

Relevant technical, policy/risk/compliance, operational, or domain expertise sufficient for the assigned
role (Phase 2). No reviewer who authored the frozen policy's rules or has a stake in its acceptance.

## Confidentiality

Reviewers access only permitted, de-identified/non-sensitive artifacts; contents and system outputs are
confidential to the pilot; no copying, export, or sharing.

## Artifact-access limits

Access is role-scoped and tenant-scoped (`access.py`). A reviewer sees only artifacts assigned to their
role, only the blinded view at Stage A, and never another reviewer's labels.

## Pseudonymous reviewer IDs

Every reviewer is `REV-A`, `REV-B`, … . Only the pseudonym appears in data, audit, and reports. The
ID→identity mapping is held separately, access-controlled, and deleted at the retention horizon.

## Conflict-of-interest disclosure (template)

> I, reviewer `<ID>`, declare the following conflicts: [artifacts I authored], [policies I own/approve],
> [reporting relationships to the pilot owner]. I will not review affected artifacts.

## Reviewer withdrawal

A reviewer may withdraw at any time; in-progress reviews are discarded, personal data deleted; completed
pseudonymous labels retained only with consent, else deleted.

## No employment-performance use

Reviewer responses, timing, and agreement are used **only** for policy calibration — never for employment
evaluation, performance review, or personnel decisions. Binding.

## No unauthorized sharing

Reviewers may not share artifacts, system outputs, or other reviewers' labels.

## Decision independence

Reviewers judge independently and blind; no reviewer sees another's label before submitting, and no one
coaches reviewers toward the system's answers on final items.

## No coaching on final items

Training (Phase 6) uses non-final artifacts only. The final set is never used to train or coach.

## Adjudicator separation

The adjudicator does not participate in the initial review of the artifacts they adjudicate and is not
influenced by reviewer identities.

## Audit

Every reviewer action (assignment, blinded label, reveal, post-reveal label, override, adjudication) is
recorded immutably with the pseudonym, role, timing, and hashes (Phase 14).

## Retention & deletion

Reviewer decision/timing data retained only for the stated calibration window, then deleted; identity
mapping deleted at or before the horizon; deletion is tenant-scoped and verifiable.

## Consent (template)

> I consent to participate; to logging of my decisions, timing, and confidence for calibration; to
> pseudonymization of my identity; and to the retention/deletion terms above. My participation is
> voluntary and revocable.

## Minimal data collection

Collect only: pseudonymous ID, role, expertise band, decisions, timing, confidence, free-text reasons. No
unnecessary personal information.
