# Security

Security here is framed primarily around **governance boundaries** enforced as
security properties. This document does not claim legal compliance, fairness, or
production certification.

## Advisory / human boundary as a security property

The separation between advisory AI output and binding human decisions is treated
as a security invariant, not merely a convention:

- AI may produce evaluations/recommendations only where existing contracts
  permit. A recommendation is **advisory** and does not mutate binding workflow
  state.
- A binding employment decision requires an authenticated, **authorized human**
  actor.
- AI, service, and system principals must never masquerade as human authority.
  An AI actor can **never** create a binding employment decision or perform a
  human-only transition.

These invariants are asserted by:

```bash
python -m ugence_ai_hiring verify
```

which prints PASS/FAIL.

## Authentication and authorization

Binding transitions require an authenticated actor whose authority is
established through the governance kernel. Authorization outcomes are recorded as
distinct records, separate from the decisions and executions they relate to.

## No secrets

The core does not read, store, or require secrets. There are no embedded
credentials and no credential-bearing configuration in the shipped package.

## No network in the core

The core is offline and deterministic. It makes no outbound network calls, uses
no AI/model SDK, and includes no database driver or web framework. The only
adapters that ship are in-memory. The optional `api` extra adds an HTTP surface
but does not change the offline, deterministic nature of the core logic.

## Execution boundary

The package may prepare governed action requests and record authorization
outcomes, but it must not execute downstream enterprise actions (no sending
offers, no ATS rejections, no payroll mutation, no candidate contact, no
production HRIS invocation). Authorization does not equal execution. See
[GOVERNANCE_BOUNDARIES.md](GOVERNANCE_BOUNDARIES.md).
