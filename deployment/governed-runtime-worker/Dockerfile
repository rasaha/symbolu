# Governed runtime worker — private hosted deployment image (composition-root ADR step 4).
#
# One OCI image packaging the governed runtime worker (deployment/governed-runtime-worker)
# and every first-party package it composes, behind one private TLS listener. Non-root,
# read-only-root compatible, no compiler or test dependency in the runtime layer, no
# secret in any layer: the two PostgreSQL DSNs are environment at run time only.
#
# The base image is the ratified python:3.11-slim-bookworm multi-arch INDEX digest the
# owner ratified for the studio image (BASE_IMAGE_MIRROR_DECISION.json). No new digest is
# introduced; ci/verify_ratified_pins.py asserts base-images.json == that record == these
# FROM lines, offline, before any other container step. Build context is the repository
# root. The FROM references stay docker.io/library/...@<digest>; CI's --build-context
# overrides make them resolve through the owner-approved mirror BY that digest, and
# docker.io is never consulted.

# ---- Stage 1: worker + composed packages -------------------------------------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS backend
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Every first-party distribution the worker imports or its dependency metadata names.
# Nothing else: no studio, no provider SDK, no model client.
COPY packages/governance-contracts /build/pkgs/governance-contracts
COPY packages/runtime/agent-runtime /build/pkgs/agent-runtime
COPY packages/risk_authority /build/pkgs/risk_authority
COPY packages/capabilities/decision-authority /build/pkgs/decision-authority
COPY packages/governance-provider-framework /build/pkgs/governance-provider-framework
COPY packages/providers/actiongate /build/pkgs/actiongate
COPY packages/integration/risk-authority-runtime /build/pkgs/risk-authority-runtime
COPY packages/integration/risk-authority-status-runtime /build/pkgs/risk-authority-status-runtime
COPY packages/integration/agent-runtime-governance /build/pkgs/agent-runtime-governance
COPY packages/integration/approval-workflow /build/pkgs/approval-workflow
COPY packages/integration/authority-directory /build/pkgs/authority-directory
COPY packages/integration/control-plane-root /build/pkgs/control-plane-root
COPY packages/integration/durable-execution /build/pkgs/durable-execution
COPY packages/integration/governed-review /build/pkgs/governed-review
COPY packages/integration/governed-review-service /build/pkgs/governed-review-service
COPY packages/integration/approver-identity-jwt /build/pkgs/approver-identity-jwt
COPY deployment/governed-runtime-worker /build/worker
RUN pip install --no-cache-dir \
      /build/pkgs/governance-contracts /build/pkgs/agent-runtime /build/pkgs/risk_authority \
      /build/pkgs/decision-authority /build/pkgs/governance-provider-framework /build/pkgs/actiongate \
      /build/pkgs/risk-authority-runtime /build/pkgs/risk-authority-status-runtime \
      /build/pkgs/agent-runtime-governance \
      /build/pkgs/approval-workflow /build/pkgs/authority-directory /build/pkgs/control-plane-root \
      /build/pkgs/durable-execution /build/pkgs/governed-review /build/pkgs/governed-review-service \
      /build/pkgs/approver-identity-jwt /build/worker

# ---- Stage 2: minimal runtime image -------------------------------------------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UGENCE_REVIEW_DATA_DIR=/var/lib/ugence-review \
    UGENCE_REVIEW_PORT=8444

# non-root fixed UID/GID; the durable volume is the only writable application path
RUN groupadd --gid 10001 ugence \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin ugence \
 && mkdir -p /var/lib/ugence-review /app && chown -R 10001:10001 /var/lib/ugence-review /app

COPY --from=backend /opt/venv /opt/venv
COPY deployment/governed-runtime-worker/EXTERNAL_DEPLOYMENT_EVIDENCE.json /app/deployment/EXTERNAL_DEPLOYMENT_EVIDENCE.json
COPY deployment/governed-runtime-worker/container-healthcheck.py /app/container-healthcheck.py

USER 10001:10001
WORKDIR /app
VOLUME ["/var/lib/ugence-review"]
EXPOSE 8444/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "/app/container-healthcheck.py"]

LABEL org.opencontainers.image.title="governed-runtime-worker" \
      org.opencontainers.image.version="0.1.1" \
      org.opencontainers.image.description="Governed runtime worker: the governed review service composition root over the DBOS engine, behind one private TLS listener. Reference-grade, shadow-only; production mode is a posture, not a certification. No LIVE execution." \
      org.opencontainers.image.source="https://github.com/rasaha/symbolu" \
      org.opencontainers.image.licenses="UNLICENSED"

ENTRYPOINT ["python", "-m", "governed_runtime_worker"]
