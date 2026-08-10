# Error Model (P3B)

`ApiError { code, message, field_path, diagnostics, request_id, safe_details }`.
No stack traces are ever returned; production mode empties `safe_details`.
Validation errors (422) carry per-field diagnostics. See
`apps/ugence-governance-studio/docs/ERROR_MODEL.md` for the full HTTP table.
