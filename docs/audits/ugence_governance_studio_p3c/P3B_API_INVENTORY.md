# P3B API Inventory (consumed by P3C)

The frozen `governance_studio.api.v1` contract exposes 23 operations. P3C consumes
exactly nine (§6):

`get_health`, `get_ready`, `get_version`, `list_scenarios`, `get_scenario`,
`get_scenario_workflow`, `get_scenario_registry`, `get_scenario_eligibility`,
`explain_eligibility`.

The remaining fourteen operations (ranking, plan, composition, permissions,
fallback, replay, comparison, what-if, adapt/validate, export) are P3D scope and
are **not** wired into navigation, controls or the typed client. Types are
generated deterministically from the committed OpenAPI JSON with
`openapi-typescript`; the source sha256 is recorded and drift-verified.
