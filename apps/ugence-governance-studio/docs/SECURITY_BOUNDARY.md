# Governance Studio API — Security Boundary (P3B)

Offline and synthetic-data-only, but designed safely:

- strict pydantic request models; unknown fields rejected (422)
- request-body size limit (default 2 MiB) enforced pre-parse → 415/413
- safe JSON only; no pickle/unsafe deserialization
- no arbitrary file paths, no file uploads, no shell/subprocess execution
- no dynamic Python imports from request data
- no external network calls during domain evaluation (socket-block test)
- sanitized exceptions (no stack traces); secure response headers
- configurable CORS (closed by default)
- rate-limit seam and authentication seam — both DISABLED by default; no
  hard-coded demo passwords. Authentication belongs to P3E.
- read-only fixture access; immutable scenario registry

Response headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
`Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and cross-origin
isolation headers.
