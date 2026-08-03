# Assertion-governance boundary

TAP owns exactly one authority: **evaluating whether a material assertion is
supported, unsupported, constrained, or indeterminate relative to supplied
evidence.**

TAP **may**: receive an assertion-governance request; inspect supplied governed
evidence references; evaluate components and qualifiers; return structured
assertion coverage, evidence coverage, unsupported elements, omitted qualifiers,
constraints, obligations, and explanation references; report health/lifecycle;
emit invocation records; and contribute assessment evidence through the framework's
neutral `AssertionAssessmentIntegration`.

TAP **must not** (and does not): authorize, dispatch, execute, reconcile, or
compensate actions; invoke an enterprise tool; make a final business decision; act
as a human authority; mutate candidate/workflow/business state; touch
`ActionControlPlanePort` or `ExternalExecutionPort`; import or depend on ActionGate;
convert an assertion result into an action authorization; or treat provider health
as a business outcome.

TAP and ActionGate are **peer providers** of different kinds. Neither imports or
invokes the other. Enforced by `tests/authority/test_authority_boundary.py` and
`tests/boundaries/test_dependency_boundaries.py`.
