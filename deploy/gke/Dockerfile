FROM python:3.11-slim AS base

WORKDIR /app

# Install only the cloud controller dependencies (pinned for reproducibility)
COPY deploy/gke/requirements-controller.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy only the symbolu package (not tests, scripts, docs, etc.)
COPY symbolu/ /app/symbolu/

# Non-root user for security
RUN groupadd -r ncc && useradd -r -g ncc -d /app -s /sbin/nologin ncc
USER ncc

# Controller runs on port 8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

ENTRYPOINT ["python", "-m", "symbolu.cloud_controller.main"]
CMD ["--config", "/etc/ncc/controller.yaml"]
