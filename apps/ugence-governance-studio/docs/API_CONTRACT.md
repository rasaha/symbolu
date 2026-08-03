# Governance Studio API — Contract (P3B)

- API contract version: `governance_studio.api.v1`
- OpenAPI: `apps/ugence-governance-studio/contracts/openapi.json` (frozen, drift-verified)
- AWC version: `0.2.1`; supported workflow contracts: `workflow_ir.v1`, `workflow_ir.v2`

## Response envelope (`ApiResponse`)
```
api_version · request_id · operation · scenario_id · source_contract_version
awc_version · input_digests · result · diagnostics · warnings · maturity
```
Rules: `request_id` and server timestamps are excluded from logical result
fingerprints; canonical AWC result fields are passed through `result` intact;
warnings never replace typed domain states; unknown request fields are rejected.

## Error envelope (`ApiError`)
```
code · message · field_path · diagnostics · request_id · safe_details
```
No stack traces are ever returned; in production mode `safe_details` is empty.
