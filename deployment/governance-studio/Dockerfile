# Governance Studio — private hosted deployment image (P3E §20).
#
# One OCI image packaging the FROZEN frontend build and the FROZEN P3B backend behind
# a single HTTPS listener with a deployment access gate. Non-root, read-only-root
# compatible, no npm/compiler/test deps in the runtime layer, no secrets, no
# production certificate. Build context is the repository root.
#
# Base images are pinned to immutable multi-arch INDEX digests (buildx selects the
# linux/amd64 child at build time). The digests are recorded in base-images.json and
# re-verified against the live registry by the CI base-image-digest-verification job;
# a pin change requires a reviewed repository change.

# ---- Stage 1: frontend build -------------------------------------------------
FROM node:22-bookworm-slim@sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46 AS frontend
WORKDIR /build/frontend
COPY apps/ugence-governance-studio/frontend/package.json apps/ugence-governance-studio/frontend/package-lock.json ./
RUN npm ci
COPY apps/ugence-governance-studio/frontend/ ./
COPY apps/ugence-governance-studio/contracts/ /build/contracts/
RUN npm run generate:api \
 && npm run verify:openapi \
 && npm run verify:api-boundary \
 && npm run verify:version \
 && npm run build

# ---- Stage 2: backend + deployment wheels -----------------------------------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS backend
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY apps/ugence-governance-studio/backend /build/backend
COPY packages/capabilities/agent-workforce-composer /build/awc
COPY packages/tooling/policy-workflow-compiler /build/compiler
# CR-2: the combined application imports the v2 surface, whose services import the
# agent runtime (dependency-free) at module import. Nothing else is added to the layer.
COPY packages/runtime/agent-runtime /build/agent-runtime
COPY deployment/governance-studio /build/deployment
RUN pip install --no-cache-dir "pydantic>=2" "fastapi>=0.110" "uvicorn>=0.27" "starlette>=0.36" \
 && pip install --no-cache-dir /build/compiler /build/awc /build/agent-runtime /build/backend /build/deployment

# ---- Stage 3: minimal runtime image -----------------------------------------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UGENCE_STUDIO_FRONTEND_DIR=/app/frontend/dist \
    UGENCE_STUDIO_SCENARIOS_ROOT=/app/data/demo_data \
    UGENCE_STUDIO_MANIFEST=/app/deployment/synthetic-scenarios-manifest.json \
    UGENCE_STUDIO_OPENAPI=/app/contracts/openapi.json \
    UGENCE_STUDIO_APPROVED_OPS=/app/frontend/security/approved-api-operations.json \
    UGENCE_STUDIO_RUNTIME_DIR=/var/run/ugence-studio \
    UGENCE_STUDIO_PORT=8443

# non-root fixed UID/GID
RUN groupadd --gid 10001 ugence && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin ugence

COPY --from=backend /opt/venv /opt/venv
COPY --from=frontend /build/frontend/dist /app/frontend/dist
COPY apps/ugence-governance-studio/frontend/security /app/frontend/security
COPY apps/ugence-governance-studio/contracts /app/contracts
COPY apps/ugence-governance-studio/demo_data /app/data/demo_data
COPY deployment/governance-studio/synthetic-scenarios-manifest.json /app/deployment/synthetic-scenarios-manifest.json
COPY deployment/governance-studio/approved-runtime-config.json /app/deployment/approved-runtime-config.json
COPY deployment/governance-studio/entrypoint.py /app/entrypoint.py
COPY deployment/governance-studio/container-healthcheck.py /app/container-healthcheck.py

# write the frontend build marker the startup gate checks
RUN python -c "from governance_studio_deployment.packaging import write_frontend_marker; write_frontend_marker('/app/frontend/dist','/app/frontend/frontend-build.json')" \
 && mkdir -p /var/run/ugence-studio && chown -R 10001:10001 /var/run/ugence-studio /app

USER 10001:10001
WORKDIR /app
EXPOSE 8443/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "/app/container-healthcheck.py"]

LABEL org.opencontainers.image.title="governance-studio-private-hosted" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.description="Private hosted, HTTPS-only, synthetic-data-only Governance Studio deployment. No permission granting, no agent execution, no business-action authorization." \
      org.opencontainers.image.source="https://github.com/rasaha/symbolu" \
      org.opencontainers.image.licenses="UNLICENSED"

ENTRYPOINT ["python", "/app/entrypoint.py"]
