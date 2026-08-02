# Pilot Reviewer Protocol

> Reviewer feedback is curated, append-only, and bound to the exact workflow
> revision. Reviewer agreement is **not** absolute ground truth. Machine-readable
> companion: `docs/pilot_reviewer_protocol.json`.

## Preferred protocol

1. the reviewer records an **initial independent** assessment;
2. the Ugence result is revealed;
3. the reviewer records agreement/disagreement and rationale.

When blinding is impossible the annotation is marked `REVIEW_NOT_BLINDED` and
independent agreement is not claimed. Where practical, a primary + optional
secondary reviewer + conflict adjudicator with pseudonymous ids and role-based
eligibility are supported.

## Curated vocabularies

- **Status**: AGREE / TOO_STRICT / TOO_LENIENT / WRONG_STATUS / INSUFFICIENT_INFORMATION.
- **Intervention**: CORRECT / UNNECESSARY / MISSING / WRONG_TYPE / WRONG_REQUIRED_AUTHORITY.
- **Root cause**: policy / source-data / freshness / conflict / adapter / change-identity /
  authority-mapping / intervention-routing / reviewer-interpretation / product-logic /
  insufficient-evidence / other-curated.
- **Incremental value**: value-beyond-CI / duplicates-existing-control / partially-useful /
  not-useful / undetermined, plus per-case labels (unique signal, earlier detection,
  better routing, better auditability, …). A unique-detection claim requires an
  evidence reference.
- **Actual outcome**: merged-*, waited, blocked-by-existing-control, abandoned,
  reverted, incident-associated, no-action, unknown. Correlation is not causation —
  a later incident does not automatically prove the original result wrong.

An annotation never modifies the original clearance or intervention record.
