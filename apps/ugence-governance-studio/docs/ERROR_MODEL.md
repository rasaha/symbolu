# Governance Studio API — Error & Domain-Result Model (P3B)

## HTTP mapping
| Status | Meaning |
|--------|---------|
| 400 | malformed request envelope / bad parameter |
| 404 | unknown scenario or resource |
| 409 | incompatible workflow/overlay conflict |
| 413 | request too large |
| 415 | unsupported media type |
| 422 | schema/input validation failure (incl. unsupported contract version) |
| 429 | rate-limit boundary (seam) |
| 500 | unexpected internal failure (sanitized) |
| 503 | service not ready |

## Typed domain results are NOT errors (HTTP 200)
`NO_ELIGIBLE_AGENT`, `NO_FEASIBLE_TEAM`, `SEARCH_SPACE_EXCEEDED`, `PARTIAL`,
`INVALID_INPUT` are valid AWC outcomes returned as ordinary 200 domain results.
They are never converted into 5xx server errors.
