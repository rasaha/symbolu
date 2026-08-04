# Operator Runbook (P3E)

- **Start / stop**: `docker compose -f .../compose.private.yml up -d` / `down`.
- **Health**: `/healthz` (liveness), `/readyz` (readiness; 503 until integrity passes).
- **Rotate credentials**: regenerate the hash offline, update `.env`, restart.
- **Rotate certificate**: replace files in the TLS dir, restart (see TLS_CERTIFICATE_OPERATIONS).
- **Logs**: structured JSON on stdout; response-body access logging is off by default.
- **Startup failure**: read the one-line failure code on stderr and the
  `/var/run/ugence-studio/startup-integrity.json` report (no secrets); fix config and restart.
- **Restart/recovery**: the service is stateless; a restart re-runs the integrity gate and
  reloads the pinned synthetic bundle. Deterministic scenario fingerprints are unchanged.
