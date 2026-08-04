# Container Hardening (P3E)

- Multi-stage build; runtime image contains no npm, no compiler toolchain, no test deps,
  no VCS metadata, no secrets, no production certificate.
- Runs as non-root **UID/GID 10001**; `WORKDIR /app`; only **8443/tcp** exposed.
- Read-only root filesystem compatible; writable state confined to `tmpfs` `/tmp` and
  `/var/run/ugence-studio`.
- Compose drops **ALL** capabilities, sets `no-new-privileges:true`, mounts certs
  read-only, bounds CPU/memory, and defines a healthcheck + restart policy.
- Base images should be pinned to immutable digests at release (tags used in-repo).
- Build/run and image vulnerability scan are **CI-gated**; they are NOT executed in a
  daemon-less environment.
