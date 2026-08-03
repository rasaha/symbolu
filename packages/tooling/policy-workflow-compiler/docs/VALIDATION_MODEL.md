# Validation Model

Validation (`validation/`) is the fail-closed gate between a policy pack and
compilation. It produces structured diagnostics and refuses to compile any pack
that carries a blocking finding.

## Severity levels

| Severity | Blocks compilation? |
| --- | --- |
| `INFO` | No |
| `WARNING` | No |
| `REVIEW_REQUIRED` | Yes |
| `ERROR` | Yes |
| `FATAL` | Yes |

Severity is **never silently reclassified**. A finding cannot be downgraded to
slip past the gate; the only governed way to proceed past a `REVIEW_REQUIRED`
gap is an explicit human approval that records the reviewed gap.

## Structured diagnostic shape

Every diagnostic is a structured object, not a free-text log line:

- `code` — the stable rule identifier (see below).
- `severity` — one of the five levels above.
- `object_id` — the object the finding is about.
- `message` — a human-readable explanation.
- `related_object_ids` — other objects implicated in the finding.
- `provenance` — provenance context for the finding.
- `suggested_remediation` — a concrete next step.

## Validation rules

| Code | Concern |
| --- | --- |
| `DUPLICATE_OBJECT_ID` | Two objects share an `object_id`. |
| `DANGLING_REFERENCE` | A reference points at no existing object. |
| `MISSING_PROVENANCE` | A substantive object cites no provenance. |
| `UNRESOLVED_AUTHORITY_REFERENCE` | An authority reference does not resolve. |
| `ACTION_CONSTRAINT_WITHOUT_AUTHORITY` | A constraint lacks a governing authority. |
| `EXCEPTION_WITHOUT_DECISION_RULE` | An exception has no rule to except. |
| `OVERRIDE_WITHOUT_DECISION_RULE` | An override has no rule to override. |
| `APPROVAL_PATH_MISSING_STEPS` | An approval path declares no steps. |
| `IMPOSSIBLE_APPROVAL_ORDERING` | Approval steps cannot be ordered. |
| `SEGREGATION_OF_DUTIES_CONTRADICTION` | Duties that must be separate collide. |
| `UNKNOWN_CAPABILITY` | A referenced capability is not in the registry. |
| `MISSING_EXPECTED_OUTCOME` | A scenario declares no expected outcome. |
| `INCOMPLETE_COVERAGE` | A required object has no assurance coverage. |
| `EMBEDDED_SECRET` | A secret-like value appears in the pack. |
| `NON_DETERMINISTIC_VALUE` | A value that would break reproducibility. |
| `UNSUPPORTED_SCHEMA_VERSION` | The pack's schema version is not supported. |
| `AUTHORITY_BOUNDARY_VIOLATION` | A node violates the authority table (FATAL). |
| `APPROVAL_REQUIRED` | Human approval is required to proceed. |

## Fail-closed behavior

The pipeline halts on the first blocking severity. There is no partial
compilation and no best-effort fallback: a pack that cannot be validated cleanly
does not become a compiled package. `INCOMPLETE_COVERAGE` (from assurance
generation) and `AUTHORITY_BOUNDARY_VIOLATION` (from authority checks) both
terminate compilation. This makes the presence of a compiled package a positive
signal that every blocking rule passed.

See `AUTHORITY_BOUNDARIES.md` for the authority table, `ASSURANCE_GENERATION.md`
for the coverage invariant, and `SECURITY_AND_FAILURE_MODEL.md` for the
`EMBEDDED_SECRET` and `NON_DETERMINISTIC_VALUE` rules in context.
