# Governance Boundaries

This is the canonical statement of the governance boundaries enforced by
`ugence-ai-hiring`. These boundaries are preserved in spirit throughout the
package and are asserted by `python -m ugence_ai_hiring verify`.

## Advisory AI boundary

AI may produce evaluations/recommendations only where existing contracts permit.
A recommendation is **advisory** and does not mutate binding workflow state.

## Human decision boundary

A binding employment decision requires an authenticated, **authorized human**
actor. AI/service/system principals must never masquerade as human authority. An
AI actor can **never** create a binding employment decision or perform a
human-only transition.

## Record separation (never collapse)

The following are distinct records and must never be collapsed into one another:

- evidence
- assessment
- recommendation
- decision
- override
- action request
- authorization response
- execution

## Execution boundary

The package **may**:

- prepare governed action requests,
- bind context,
- request authorization, and
- record authorization outcomes.

The package **must not**:

- execute downstream enterprise actions,
- send offers,
- reject candidates in an ATS,
- mutate payroll,
- contact candidates,
- invoke production HRIS, or
- claim that authorization equals execution.

## Legal-claim boundary

The package does **not** claim to guarantee:

- legal compliance,
- fairness,
- non-discrimination,
- employment-law satisfaction,
- validated bias detection, or
- production certification.

`production_certified` is always `False`.
