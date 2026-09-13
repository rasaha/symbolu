# MEU validation job — a GCP Cloud Run **Job** image for the commissioning validation.
#
# It is a job, not a service: no port is exposed, no listener is started, nothing can
# call it. The operator executes it and it runs to completion.
#
#   NO SECRET IS IN ANY LAYER. The image contains code, pinned dependencies and a
#   configuration FILE PATH. The pinned Secret Manager version is read at run time by
#   the job's own composition root, under the Cloud Run Job's attached service account,
#   and only after the execution posture and the seventeen step-8 designations pass.
#
# The base image is the python:3.11-slim-bookworm multi-arch INDEX digest already
# ratified for this repository's images (deployment/governed-runtime-worker/base-images.json).
# No new digest is introduced by this deployment unit. Build context is the repository root.

# ---- Stage 1: the job and the four distributions it composes ------------------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS build
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY packages/integration/model-egress-unit            /build/pkgs/model-egress-unit
COPY packages/integration/model-egress-provider-openai /build/pkgs/model-egress-provider-openai
COPY packages/integration/model-egress-validation      /build/pkgs/model-egress-validation
COPY packages/integration/model-egress-custody-gcp     /build/pkgs/model-egress-custody-gcp
COPY deployment/meu-validation-job                     /build/job

# -c: the exact deployment pins (constraints.txt). The `[google]` extra is what brings
# the real Secret Manager client into the image; the distributions themselves declare it
# as an optional extra so the package suites install and run without it.
RUN pip install --no-cache-dir -c /build/job/constraints.txt \
      /build/pkgs/model-egress-unit \
      /build/pkgs/model-egress-provider-openai \
      /build/pkgs/model-egress-validation \
      "/build/pkgs/model-egress-custody-gcp[google]" \
      /build/job

# ---- Stage 2: the runtime image ------------------------------------------------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEU_JOB_CONFIG=/etc/meu-validation-job/config.json

RUN groupadd --gid 10001 ugence \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin ugence \
 && mkdir -p /app /var/lib/meu-validation-job /etc/meu-validation-job \
 && chown -R 10001:10001 /var/lib/meu-validation-job

COPY --from=build /opt/venv /opt/venv
COPY deployment/meu-validation-job/entrypoint.py /app/entrypoint.py

# The job holds no credential and writes only its report, so it runs unprivileged with a
# read-only root filesystem; the report path is the one writable location it needs.
USER 10001:10001
WORKDIR /app

LABEL org.opencontainers.image.title="meu-validation-job" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.description="MEU commissioning validation job (Cloud Run Job). Offline by default; live fails closed; no genuine dispatch path exists in this slice. Holds no credential." \
      org.opencontainers.image.source="https://github.com/rasaha/symbolu" \
      org.opencontainers.image.licenses="UNLICENSED"

ENTRYPOINT ["python", "/app/entrypoint.py"]
CMD ["validate"]
