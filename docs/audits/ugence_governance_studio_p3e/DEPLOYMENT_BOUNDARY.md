# Deployment Boundary (P3E)

```
HTTPS (8443, TLS1.2+)
      │  trusted-host validation
      ▼
  deployment access gate (HTTP Basic, bounded failures)
      │  origin + X-Ugence-Request on mutating API requests
      ▼
  security headers + 1 MiB body cap
      ▼
  ┌───────────────┬──────────────┬─────────────────────────┐
  │ SPA (/,assets)│ /healthz     │ frozen backend /api/v1  │
  │               │ /readyz      │ + /health /ready /version│
  └───────────────┴──────────────┴─────────────────────────┘
                                   synthetic-only catalog (pinned+hashed)
```

- **One** OCI image, **one** HTTPS listener, **one** application port `8443/tcp`.
- No plaintext application listener. No separate frontend/backend port.
- Only `/healthz` and `/readyz` are unauthenticated and expose minimal info.
- Unknown `/api/*` paths are **not** routed into the SPA (backend 404).
- The deployment adds only `/healthz` and `/readyz` outside the frozen `/api/v1`
  contract — the OpenAPI contract is unchanged.
- No outbound Internet access is required at runtime (verified: no non-loopback egress).
