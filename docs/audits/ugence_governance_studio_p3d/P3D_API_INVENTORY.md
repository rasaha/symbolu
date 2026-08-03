# P3D API Inventory (consumed by the planning explorer)

The frozen `governance_studio.api.v1` contract exposes **23 operations**
(OpenAPI sha256 `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656`,
unchanged by this phase). P3D consumes **17** of them.

## Carried over from P3C (9)

`get_health`, `get_ready`, `get_version`, `list_scenarios`, `get_scenario`,
`get_scenario_workflow`, `get_scenario_registry`, `get_scenario_eligibility`,
`explain_eligibility`.

## Newly consumed by P3D (8)

| Operation | Screen / use | HTTP |
|-----------|--------------|------|
| `get_scenario_ranking` | Ranking Explorer | `GET /api/v1/scenarios/{id}/ranking` |
| `get_scenario_plan` | Composition Explorer | `GET /api/v1/scenarios/{id}/plan` |
| `explain_plan` | Composition (non-greedy explanation) | `POST /api/v1/explanations/plan` |
| `explain_ranking` | Ranking (score decomposition) | `POST /api/v1/explanations/ranking` |
| `replay_plan` | Plan Replay | `POST /api/v1/plans/replay` |
| `compare_plans` | Plan Comparison | `POST /api/v1/plans/compare` |
| `scenario_what_if` | Controlled What-If | `POST /api/v1/scenarios/{id}/what-if` |
| `export_scenario` | Deterministic export | `GET /api/v1/scenarios/{id}/export` |

## Not consumed (6) — remain backend-internal / P3E+

`validate_workflow`, `adapt_workflow`, `compare_adaptations`,
`evaluate_eligibility`, `evaluate_ranking`, `compose_workforce`.

These are lower-level orchestration primitives the composed read/POST operations
already wrap; the browser never calls them directly. Types are generated
deterministically from the committed OpenAPI JSON with `openapi-typescript`; the
source sha256 is recorded in `src/generated/openapi.hash.json` and drift-verified
in CI (`openapi-client-freeze`).
