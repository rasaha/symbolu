# Configuration Reference (P3E)

| Variable | Required | Meaning |
|----------|----------|---------|
| `UGENCE_STUDIO_DEPLOYMENT_MODE` | no | `production` (default) or `test` (loopback) |
| `UGENCE_STUDIO_USERNAME` | yes | operator username (no default) |
| `UGENCE_STUDIO_PASSWORD_HASH` | yes | `scrypt$…` hash (no default; generated offline) |
| `UGENCE_STUDIO_ALLOWED_HOSTS` | yes (prod) | comma-separated Host allowlist; wildcard rejected |
| `UGENCE_STUDIO_TLS_CERT_FILE` | yes | PEM certificate path |
| `UGENCE_STUDIO_TLS_KEY_FILE` | yes | PEM private key path (read-only mount) |
| `UGENCE_STUDIO_TRUSTED_PROXY` | no | `1` to trust `X-Forwarded-For` (only behind a real proxy) |
| `UGENCE_STUDIO_PORT` | no | application port (default 8443) |
| `UGENCE_STUDIO_ACCESS_LOG` | no | `1` to enable access logging (off by default) |

Frozen packaged paths (`FRONTEND_DIR`, `SCENARIOS_ROOT`, `MANIFEST`, `OPENAPI`,
`APPROVED_OPS`) are set by the image and should not be overridden in production.
