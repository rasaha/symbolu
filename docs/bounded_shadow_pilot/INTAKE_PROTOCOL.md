# Natural-Artifact Intake Protocol (Phase 2)

*`bounded_shadow_pilot/intake_protocol.py`. Turns a naturally occurring repository artifact into a
pilot-eligible, de-identified, use-case-classified record — or fails closed. Adds a natural-artifact
layer on top of the inherited, read-only shadow-grade controls; re-implements no decision logic.*

## Composition (read-only reuse)

- `customer_shadow_readiness.intake.intake` — bounds (≤ 20 000 chars), format, classification,
  permitted-use, redaction.
- `customer_shadow_readiness.data_controls` — `classify`, `permitted_use`, `redact`.

The pilot fixes the request clearance at **`internal`**: the pilot handles de-identified / permitted
data only, so any artifact the inherited classifier marks **`restricted`** (PII/PHI/secret markers) is
not permitted under this clearance and fails closed.

## Fail-closed decision order

| # | Check | Reject code |
|---|---|---|
| 1 | Provenance — kind ∈ {doc, docstring, comment}, real path | `INTAKE.UNKNOWN_PROVENANCE` |
| 2 | Hard exclusion — clinical / trading / permission-change / deletion / employment / legal / autonomous-security markers | `INTAKE.EXCLUDED_USE_CASE` |
| 3 | Inherited intake — empty / oversize / malformed | `INTAKE.EMPTY` / `INTAKE.OVERSIZE` / `INTAKE.BAD_FORM` |
| 3 | Inherited permitted-use — PII/restricted under de-identified clearance | `INTAKE.PROHIBITED_DATA` |
| 4 | Eligible use-case assignment | `INTAKE.UNCLASSIFIABLE_USE_CASE` |
| ✓ | Accepted | `INTAKE.ACCEPTED` |

Exclusion (step 2) runs **before** classification so an excluded artifact can never be accepted even
if it would otherwise classify cleanly. Nothing in the order is permissive: every branch either
rejects or advances to a stricter check.

## Use-case assignment (deterministic)

An accepted artifact is assigned exactly one **eligible** use case by first-match keyword signature,
defaulting to `software_engineering_recommendation_review` because the host repository is a software
governance codebase. The eligible set is exactly the nine advisory/review use cases from
`PILOT_SCOPE.md`; the excluded set is enforced by `_EXCLUDED_MARKERS` at step 2.

## Output record

`NaturalIntakeRecord`: `accepted`, `artifact_id` (`nat-<sha16>` over path+kind+text), `source_path`,
`source_kind`, `use_case`, `artifact_class`, `redacted_text` (raw text is never retained
unredacted), `char_len`, `reason_codes`.

## Determinism & non-enforcement

Pure functions of the input text and its provenance; no wall-clock, no randomness, no I/O in the
decision path; nothing is enforced. The same artifact always yields the same record and the same
`artifact_id`.
