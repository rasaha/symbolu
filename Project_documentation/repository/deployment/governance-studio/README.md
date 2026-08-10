# Governance Studio — Private Hosted Deployment (P3E)

One OCI container packaging the **frozen** Governance Studio frontend (`0.2.0`) and P3B
backend (`0.1.0`, `governance_studio.api.v1`) behind a single HTTPS listener with a
deployment access gate and synthetic-data-only enforcement. Deployment bundle version
**0.1.0** (`governance-studio-private-hosted`).

**Does not**: grant permissions · provision credentials · authorize business actions ·
execute agents · call external models/tools · use production data · run multitenant.

## Quick start (local test mode)

```bash
# 1. generate an operator password hash (offline; prints only the hash)
python -m governance_studio_deployment.generate_password_hash

# 2. run over the committed test certificate on loopback (development only)
UGENCE_STUDIO_DEPLOYMENT_MODE=test \
UGENCE_STUDIO_USERNAME=operator \
UGENCE_STUDIO_PASSWORD_HASH='scrypt$...' \
UGENCE_STUDIO_TLS_CERT_FILE=deployment/governance-studio/tests/certs/server.crt \
UGENCE_STUDIO_TLS_KEY_FILE=deployment/governance-studio/tests/certs/server.key \
UGENCE_STUDIO_FRONTEND_DIR=apps/ugence-governance-studio/frontend/dist \
UGENCE_STUDIO_SCENARIOS_ROOT=apps/ugence-governance-studio/demo_data \
UGENCE_STUDIO_MANIFEST=deployment/governance-studio/synthetic-scenarios-manifest.json \
python -m governance_studio_deployment
```

## Container (requires a Docker daemon)

```bash
docker compose -f deployment/governance-studio/compose.private.yml build
cp deployment/governance-studio/.env.example deployment/governance-studio/.env   # fill in; never commit
docker compose -f deployment/governance-studio/compose.private.yml up
curl -k https://localhost:8443/readyz
```

## Tests

```bash
cd deployment/governance-studio && python -m pytest   # startup integrity, auth, HTTPS/TLS,
# host/origin, headers, limits, logging, synthetic boundary, governance boundary,
# packaged E2E (4 scenarios), runtime egress, container-artifact structure
```

See `apps/ugence-governance-studio/docs/p3e/` for the operator/security runbooks and
`docs/audits/ugence_governance_studio_p3e/` for the audit trail. The image build/run and
container scan are CI-gated; a daemon-less environment reports them NOT_EXECUTED.
