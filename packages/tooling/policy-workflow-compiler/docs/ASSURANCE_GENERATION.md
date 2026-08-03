# Assurance Generation

Assurance generation (`compiler/assurance_generation.py`) produces the assurance
package that accompanies every compiled workflow IR. It emits deterministic test
**specifications** — not Python source — and a coverage matrix that ties tests
back to policy objects.

## Test categories

Fourteen categories ensure a policy is exercised from every governed angle:

| Category | Exercises |
| --- | --- |
| `POSITIVE` | The intended happy path. |
| `NEGATIVE` | A path that must be rejected. |
| `MISSING_EVIDENCE` | Behavior when required evidence is absent. |
| `AUTHORITY_CONFLICT` | A conflict in authority. |
| `SEGREGATION_OF_DUTIES` | Separation-of-duties enforcement. |
| `EXCEPTION` | A governed exception carve-out. |
| `OVERRIDE_VALID` | A valid override. |
| `OVERRIDE_INVALID` | An override that must be refused. |
| `LEGITIMATE_COUNTEREXAMPLE` | A benign case that must not trip a risk pattern. |
| `REPLAY` | Deterministic replay of a recorded case. |
| `ACTION_CONSTRAINT` | An action constraint boundary. |
| `UNKNOWN_STATE` | Behavior in an unmodeled state. |
| `TIMEOUT` | Behavior on timeout. |
| `INDETERMINATE` | Behavior when no determinate outcome exists. |

## Test specification shape

Each generated test is a declarative specification:

- `test_id` — deterministic identifier.
- `source_object_ids` — the policy objects the test covers.
- `initial_facts` — facts present at the start.
- `actor_identities` — the actors involved.
- `evidence` — evidence supplied.
- `requested_action` — the action under test.
- `expected_outcome` — a `terminal_state`, `reason_codes`, and `audit_events`.

Because the output is a specification rather than executable code, it is stable,
reviewable, and portable to any conforming runtime harness.

## Coverage matrix and the coverage invariant

A coverage matrix maps each policy object to the tests that exercise it.
Compilation enforces a hard invariant: it **fails with `INCOMPLETE_COVERAGE`** if
any required object lacks coverage. The required objects are:

- `DecisionRule`
- `ProhibitedCondition`
- `ExceptionRule`
- `OverrideRule`
- `AuthorityRequirement`
- `ActionConstraint`
- `LegitimateCounterexample`

This guarantees that no governed rule reaches a compiled package without at least
one test specification asserting its behavior. In the Procurement demo, assurance
generation produces 27 test specifications for the compiled workflow.

See `VALIDATION_MODEL.md` for `INCOMPLETE_COVERAGE` as a blocking diagnostic and
`AUDIT_SCHEMA.md` for the audit events referenced in expected outcomes.
