# Incident Response (P3E)

- **Suspected credential compromise**: rotate the password hash offline, update `.env`,
  restart; review logs for repeated 401 cooldowns (no credentials are logged).
- **Certificate issue**: rotate per TLS_CERTIFICATE_OPERATIONS; startup fails closed on
  invalid/expired material.
- **Integrity failure at startup**: the container exits nonzero with a precise code and
  does not bind the port; inspect `startup-integrity.json`, fix config/bundle, restart.
- **Unexpected behavior**: because the deployment is synthetic-only and stateless, the
  safest response is stop → verify image digest/SBOM → redeploy the known-good image.
- **Scope note**: there is no production data, no execution, and no authorization surface
  to contain; there is no persistent store to purge.
