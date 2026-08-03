# Result Equivalence Plan — P2.1

The equivalence harness (`compatibility.compare_adaptations` /
`compare_workforce_plans`) compares `workflow_ir.v1 + full overlay` against
`workflow_ir.v2 + reduced overlay` for the same logical workflow.

## Classification

| State | Meaning | Where used |
|---|---|---|
| `BYTE_IDENTICAL` | fingerprints and canonical serialization match | node dispositions |
| `SEMANTICALLY_EQUIVALENT` | planning projection identical; fingerprints legitimately differ (v2 provenance / source contract) | adaptations, plans |
| `INTENTIONALLY_DIFFERENT` | a typed, explained, approved difference | (none in P3A scenarios) |
| `INCOMPATIBLE` | planning outcome differs unexpectedly | failure |

## Result for the four P3A scenarios (recomputed + committed)

| Scenario | node dispositions | adaptation | plan outcome | v1/v2 plan state |
|---|---|---|---|---|
| procurement | BYTE_IDENTICAL | SEMANTICALLY_EQUIVALENT | SEMANTICALLY_EQUIVALENT | COMPLETE / COMPLETE |
| customer_support | BYTE_IDENTICAL | SEMANTICALLY_EQUIVALENT | SEMANTICALLY_EQUIVALENT | COMPLETE / COMPLETE |
| cybersecurity_success | BYTE_IDENTICAL | SEMANTICALLY_EQUIVALENT | SEMANTICALLY_EQUIVALENT | COMPLETE / COMPLETE |
| cybersecurity_no_feasible_team | BYTE_IDENTICAL | SEMANTICALLY_EQUIVALENT | SEMANTICALLY_EQUIVALENT | NO_FEASIBLE_TEAM / NO_FEASIBLE_TEAM |

Zero intentional differences and zero incompatibilities. The planning projection
(assignments, eligibility fills, fallbacks, permissions, non-agent nodes) is
identical; raw plan fingerprints differ because v2 carries richer provenance and a
different source contract — reported honestly as SEMANTICALLY_EQUIVALENT, never
claimed as byte identity.
