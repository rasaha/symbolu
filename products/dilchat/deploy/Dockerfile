# DilChat backend image (production-readiness round PR-C).
#
# ONE image, TWO processes — the web/API and the outbox relay run the same code
# with different commands and, critically, DIFFERENT DATABASE ROLES
# (DEC-3C-4 / I6): the web process connects as dilchat_app and never acquires
# the worker's outbox privileges; the relay connects as dilchat_worker. Role
# separation is enforced by the DSN each process is given (and by RLS in the
# database), never by anything inside this image.
#
# Migrations are NOT run by either process — they run as the owner role, as a
# separate step (see the operations runbook). A process that could migrate could
# also bypass the RLS posture it runs under.
#
# Build context is products/dilchat:
#   docker build -f deploy/Dockerfile -t dilchat-backend:dev .
#
# Run the web process (default):
#   docker run --env-file .env -p 8080:8080 dilchat-backend:dev
# Run the relay (worker DSN, no ports — it serves no HTTP surface):
#   docker run --env-file .env.relay dilchat-backend:dev python -m ugence_dilchat.relay

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Build wheels for the runtime dependency set only. The `swiss`, `test`, and
# `dev` extras are deliberately excluded: pyswisseph is AGPL and dev/test-only
# (DEC-007), and no production image ships a test toolchain.
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip build \
    && python -m pip wheel --wheel-dir /wheels .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Non-root runtime user. The image holds no secrets and no writable state; the
# heartbeat directory below is the only path either process writes.
RUN groupadd --system --gid 10001 dilchat \
    && useradd --system --uid 10001 --gid dilchat --home-dir /app --shell /usr/sbin/nologin dilchat

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels ugence-dilchat \
    && rm -rf /wheels

# Migrations and operational scripts travel with the image so the migration step
# and the validation scripts run the exact code the processes run.
COPY --chown=dilchat:dilchat alembic.ini ./alembic.ini
COPY --chown=dilchat:dilchat migrations ./migrations
COPY --chown=dilchat:dilchat scripts ./scripts

RUN mkdir -p /var/run/dilchat && chown dilchat:dilchat /var/run/dilchat
USER dilchat

EXPOSE 8080

# Liveness/readiness for the WEB process. The relay has no HTTP surface; its
# container healthcheck is heartbeat-file freshness (see docker-compose.pilot.yml).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/v1/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "ugence_dilchat.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
