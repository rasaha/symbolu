# API Client Generation

`npm run generate:api` runs `openapi-typescript` over the frozen
`../contracts/openapi.json`, emitting `src/generated/api.ts` with the source
sha256 in its header and a machine-readable `openapi.hash.json`. `npm run
verify:openapi` regenerates and fails on any drift, missing/renamed operation or
unsupported contract version. The envelope is typed from OpenAPI; the `Any`
`result` payloads are projected via documented view-models in `src/api/types.ts`.
