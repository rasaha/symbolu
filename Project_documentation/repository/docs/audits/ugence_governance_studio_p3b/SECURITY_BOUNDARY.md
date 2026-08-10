# Security Boundary (P3B)

Strict request models; unknown-field rejection; pre-parse body-size limit
(415/413); safe JSON only (no pickle); no arbitrary file paths; no shell/
subprocess; no dynamic imports from request data; no external network during
domain evaluation; sanitized exceptions; secure response headers; configurable
CORS (closed by default); disabled-by-default rate-limit and authentication
seams (no hard-coded passwords); read-only immutable fixtures. Enforced by
`tests/test_security.py`, `test_validation.py`, `test_architecture.py`.
