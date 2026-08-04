# Deployment Guide (P3E)

1. **Generate credentials** (offline): `python -m governance_studio_deployment.generate_password_hash` → copy the `scrypt$…` hash.
2. **Provide TLS material**: place `server.crt` + `server.key` in a directory mounted read-only; never commit the key.
3. **Configure** via `.env` (copy `.env.example`): `UGENCE_STUDIO_USERNAME`, `UGENCE_STUDIO_PASSWORD_HASH`, `UGENCE_STUDIO_ALLOWED_HOSTS`, `UGENCE_STUDIO_TLS_DIR`.
4. **Build**: `docker compose -f deployment/governance-studio/compose.private.yml build` (build context = repo root).
5. **Run**: `docker compose -f deployment/governance-studio/compose.private.yml up`.
6. **Verify readiness**: `curl -k https://<host>:8443/readyz` → `{"status":"ready",...}`.
7. **Access**: browse `https://<host>:8443/` and authenticate with the configured credentials.

Production is the default mode; startup fails closed if credentials, TLS material, or
allowed hosts are missing. Local testing only: `UGENCE_STUDIO_DEPLOYMENT_MODE=test`
(loopback + committed test cert).
