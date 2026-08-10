# OpenAPI Consumption Plan

- **Source**: the frozen `contracts/openapi.json` (sha256 `dc309eab…`).
- **Generation**: `openapi-typescript` → `src/generated/api.ts`, with
  `openapi.hash.json` recording the source hash + operation ids.
- **Drift**: `npm run verify:openapi` regenerates and fails on any difference,
  missing required operation, changed operation id, or unsupported contract
  version. Enforced in CI (`openapi-client-freeze`).
- **`result` typing**: the envelope is typed from OpenAPI; the backend types the
  envelope's `result` as `Any`, so the payload shapes are hand-written
  **presentation view-models** in `src/api/types.ts` — the single documented
  exception to the no-`any` rule. No canonical field is otherwise `any`.
