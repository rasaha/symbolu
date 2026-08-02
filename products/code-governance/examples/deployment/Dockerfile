# Minimal container for the Code Governance read-only pilot operator (MVP 1E).
#
# Read-only + shadow-only: no GitHub write path, no execution, no reservation.
# The image bakes in NO credentials and NO test secrets, runs as a non-root user,
# exposes no network listener, mounts a durable-data directory, and defaults to no
# active pilot — an explicit command is required to do anything.
FROM python:3.11-slim

# Non-root user.
RUN useradd --create-home --uid 10001 cgpilot

WORKDIR /app

# Install the product + its capability dependencies (built wheels mounted at build).
# In a real build these come from an internal index; here we document the shape.
COPY dist/ /tmp/dist/
RUN pip install --no-cache-dir /tmp/dist/*.whl || true

# Durable data lives on a mounted volume, owned by the non-root user.
RUN mkdir -p /data/cg-pilot && chown -R cgpilot:cgpilot /data/cg-pilot
VOLUME ["/data/cg-pilot"]

USER cgpilot

# Credentials are supplied at runtime via environment (never baked in):
#   -e CG_PILOT_GITHUB_READONLY_TOKEN=...   (read-only)
# No network port is exposed; the operator is a CLI + durable store, not a server.

# Default to no active pilot: the entrypoint only prints the version + status.
# Starting a pilot requires an explicit command (e.g. `cg-pilot validate`,
# `cg-pilot security-scan`, or the Python operator API).
ENTRYPOINT ["cg-pilot"]
CMD ["version"]
