# Permission-Scope Terminology (C2)

**Invariant.** Displayed: permission *requirements* used during eligibility. Not
displayed: AWC permission *proposals* produced during composition.

P3C displays: role-required permissions, prohibited permissions, agent-requested
permissions, authority ceilings, and policy-related permission failures in the
eligibility explanation. These are legitimate eligibility inputs and remain
visible on the role and registry screens.

P3C does NOT implement (P3D+): permission-proposal UI, proposed-permission bundle
comparison, permission-feasibility composition UI, permission-granting UI, or
runtime permission provisioning.

Enforcement: the terminology verifier bans permission-proposal / granting /
provisioning phrases (without colliding with the correct negated "No permission
granting" banner); a role-screen note states the boundary; `permission-scope.test`
asserts requirements are displayed and no P3D proposal UI/navigation exists; CI runs
`permission-scope-terminology`. The broad "No permission UI" claim is replaced
everywhere by this precise boundary.
