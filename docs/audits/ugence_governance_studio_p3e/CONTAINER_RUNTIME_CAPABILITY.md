# Container Runtime Capability (P3E completion probe)

Probed live before any container work.

| Capability | Result |
|------------|--------|
| `docker` client | 29.3.1 (Community) |
| `dockerd` daemon | **startable and running** (started manually; API on `/var/run/docker.sock`) |
| `docker info` server | Server 29.3.1, overlayfs, buildkit initialized, 4 CPU / 15.7 GiB |
| `docker buildx` | v0.31.1 (functional — `FROM scratch` build succeeds) |
| `docker compose` | v5.1.1 |
| Build images that need **no base pull** (`FROM scratch`) | ✅ works |
| Pull a base image (`python:3.11-slim-bookworm`) | ❌ **403 Forbidden** |
| Pull an alternative base (`ghcr.io/...`) | ❌ **403 Forbidden** |
| `docker manifest inspect` (resolve base digest) | ❌ **403 Forbidden** |
| PyPI / npm registries (allowlisted) | ✅ reachable (wheels + npm packages install) |
| `argon2-cffi` from PyPI | ✅ installable |

## Exact missing capability

The organization **egress proxy denies all container-registry blob traffic**. The
agent proxy status reports a policy denial:

```
connect_rejected: gateway answered 403 to CONNECT (policy denial or upstream failure)
host: production.cloudfront.docker.com:443
```

Docker Hub layer blobs (`production.cloudfront.docker.com`) and GHCR blobs
(`pkg-containers.githubusercontent.com`) both return **403**. The proxy README states
policy denials (403/407) must be **reported, not retried or bypassed**.

## Consequence for the container gates

- The P3E `Dockerfile` uses `FROM python:3.11-slim-bookworm` and `FROM node:22-...`;
  neither base can be pulled, and their digests cannot be resolved for pinning.
- Therefore **C2** (digest-pinned base images), **C4** (image build), and every gate
  that requires a **built/running image** (**C5–C19**) cannot execute here.
- `dockerd`/buildx/compose are fully functional; the block is **network egress policy**,
  not a missing runtime. A `FROM scratch` substitute image is **not** built — it could
  not satisfy C2/C15/C18 (no real distro base to pin or scan) and would present a
  non-representative artifact as "the P3E image", which would be dishonest.

## What remains executable (and is done in this pass)

- **§5 Argon2id password hardening** — `argon2-cffi` installs from the allowlisted PyPI,
  correcting the earlier "argon2 unavailable" conclusion. Implemented and tested.
- Source-level Python/npm dependency audits.
- Application-level regression and deployment test suites.

Container build/run/scan remain `NOT_EXECUTED` — reported honestly, never as passed.
