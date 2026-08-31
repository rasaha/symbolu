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

## Forward design (Hiring Decision Authority)

The reconstruction in
[HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md](HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md)
**preserves every boundary above** and adds governed controls in front of the
execution boundary rather than relaxing it:

- Policy is authored declaratively and **compiled** by the Hiring Policy Compiler
  (PWC) into a signed, content-addressed `HiringWorkflowIR`; the Decision
  Contract cites its IR digest (reproducible, tamper-evident).
- The **Overall Fit Index is analytics-only** and never enters the Decision
  Authority or any decision/recommendation/action object.
- A **Hiring ActionGate** denies any action whose salary/level/role/location/
  approvals deviate from the contract; deviation requires reauthorization.
- **Runtime Assurance** re-validates approvals/references/background-check/offer/
  salary-policy/requisition immediately before any HRIS/ATS write; it is
  fail-closed and never silently writes. This still lives **outside** this
  package's execution boundary — the package prepares and requests; the kernel's
  ports execute.

## Legal-claim boundary

The package does **not** claim to guarantee:

- legal compliance,
- fairness,
- non-discrimination,
- employment-law satisfaction,
- validated bias detection, or
- production certification.

`production_certified` is always `False`.
