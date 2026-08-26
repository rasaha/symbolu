# Authorization Boundary

ActionGate evaluates **whether a proposed action is authorized** under the supplied
authority, policy, risk, evidence, and decision context. It returns an authorization
outcome. **It does not dispatch, execute, observe, reconcile, or compensate the
action.**

## ActionGate MAY
- accept a neutral action-governance request;
- map it to a native ActionGate request;
- evaluate policy and authority;
- return an authorization outcome (AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE / EXPIRED);
- return constraints, obligations, an authorization expiry, authority basis, reason codes;
- preserve correlation, trace, and idempotency data;
- report health and lifecycle state; emit provider-level invocation records;
- participate through the neutral governance-provider framework.

## ActionGate MUST NOT
- dispatch, call an enterprise tool, execute, observe execution, or claim execution succeeded;
- reconcile, compensate, retry enterprise execution, or mutate enterprise state;
- create a final business decision or replace Decision Authority;
- impersonate a human authority or issue new authority to itself;
- treat authorization as proof of execution, or treat health status as authorization;
- silently elevate missing authority;
- depend on TAP or absorb TAP assertion-governance logic.

These prohibitions are enforced by
`tests/authority/test_authority_boundary.py`,
`tests/boundaries/test_dependency_boundaries.py`, and the provider's absence of any
`dispatch` / `execute` / `observe` / `reconcile` / `compensate` attribute.
