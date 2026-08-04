# Security Model (P3E)

- **Authentication**: HTTP Basic over HTTPS on every path except `/healthz`/`/readyz`.
  Constant-time comparison; bounded per-source failure cooldown; generic 401s.
- **Transport**: TLS 1.2+ only (1.0/1.1 disabled, 1.3 enabled); no plaintext app listener.
- **Cross-origin**: trusted-host allowlist; mutating API requests require a same-origin
  Origin (when present) and the `X-Ugence-Request: GovernanceStudio` header (a request
  constraint, not authorization).
- **Headers**: HSTS, strict CSP (`'self'`, no `unsafe-eval`/`unsafe-inline`/wildcards),
  nosniff, no-referrer, COOP/CORP same-origin, frame-ancestors none, no-store on API.
- **Limits**: 1 MiB body cap; request/idle timeouts; no upload surface.
- **Data**: synthetic-only, pinned + hashed, fail closed.
- **Secrets**: never logged; private key never baked into the image.
- **No authorization**: proposes only — no granting, provisioning, execution, or business action.
