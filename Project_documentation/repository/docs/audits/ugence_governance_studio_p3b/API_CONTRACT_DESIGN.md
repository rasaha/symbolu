# API Contract Design (P3B)

- Versioned prefix `/api/v1`; operational endpoints (`/health`, `/ready`,
  `/version`) unprefixed.
- One `ApiResponse` envelope for all domain endpoints; one `ApiError` envelope
  for failures. Request models are strict (`extra="forbid"`).
- OpenAPI advertises title `Ugence Governance Studio API`, version
  `governance_studio.api.v1`, AWC `0.2.1`, workflow contracts `workflow_ir.v1` +
  `workflow_ir.v2`. Generated deterministically and frozen at
  `contracts/openapi.json` (23 operations).
- Domain / scenario inputs accept a `scenario_id` reference or fully inline pinned
  artifacts; no path/code/script field exists.
