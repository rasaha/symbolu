# Health and Readiness (P3E)

- **`/healthz`** (liveness): unauthenticated, cheap, returns `{"status":"ok"}`. Never
  performs expensive checks.
- **`/readyz`** (readiness): unauthenticated, returns `{"status":"ready","deployment":
  "governance-studio-private-hosted"}` with 200 only when startup integrity passed, the
  frontend build loaded, the synthetic bundle verified, the credential gate configured,
  TLS is active, and the frozen backend imported; otherwise 503. No internal details are
  exposed in the body — detailed failures go to the startup log and
  `/var/run/ugence-studio/startup-integrity.json`.
