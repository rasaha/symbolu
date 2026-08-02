# Authority Boundary

> **The one invariant:** Action Clearance may preserve, narrow, hold, escalate, or
> block an existing authorization. It may never create authority, broaden
> authorization, replace ActionGate, dispatch execution, or own authoritative
> one-time consumption.

Action Clearance assumes ActionGate authorization **already exists** (carried by
reference + fingerprint). The evaluator structurally cannot:

- accept an unauthenticated arbitrary action as authorization, or mint one;
- turn an ActionGate `DENIED`/`INDETERMINATE`/`EXPIRED` outcome into a CLEAR result
  (only `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS` are eligible; anything else
  fail-closes to `BLOCK` with `AUTHORIZATION_NOT_ELIGIBLE`);
- add permitted actions/targets, expand parameter values, extend authorization
  expiry, remove an upstream obligation, replace the authorized actor, or change
  the authorized artifact;
- choose an execution provider, dispatch, reserve one-time execution, or persist.

**Monotonicity:** effective permissions ⊆ authorized permissions. For compatible
constraints, `effective_constraints = authorization_constraints ∩ clearance_constraints`
(clearance may only narrow). A conflict yields `CONSTRAINT_CONFLICT → ESCALATE`
(or `BLOCK` by policy); a constraint kind with no interpretation rule fails closed
(`CONSTRAINT_INTERPRETATION_UNSUPPORTED → ESCALATE`). Upstream obligations are
always preserved (`effective_obligations ⊇ authorization_obligations`).
