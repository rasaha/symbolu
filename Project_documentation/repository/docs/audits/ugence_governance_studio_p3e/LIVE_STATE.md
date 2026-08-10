# Governance Studio P3E — Live-State Audit

| Item | Value |
|------|-------|
| Live default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default-branch tip | `e496a67978245e57bb9dcbfab2387a3af18781b4` |
| PR #1323 (P3D) state | **merged** |
| PR #1323 merged_at | 2026-08-04T03:05:29Z |
| PR #1323 head commit | `8b9042426e3e113ab48b1ce100db192508e4b2ab` |
| PR #1323 merged_by | rasaha |
| P3D merged into default | yes (`8b904242` is an ancestor of the default tip) |
| Working branch | `claude/governance-studio-p3e-private-hosted` (fresh from default tip) |
| Frontend version | 0.2.0 |
| Backend API version | 0.1.0 |
| API contract | `governance_studio.api.v1` |
| AWC version | 0.2.1 |
| Compiler version | 0.2.0 |
| OpenAPI sha256 | `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656` (unchanged) |
| Platform-freeze digest | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` (unchanged) |

## Environment constraint (recorded honestly)

This build environment has the Docker **CLI** but **no running Docker daemon**
(`/var/run/docker.sock` absent) and no rootless alternative. The OCI image therefore
cannot be **built or run** here. All deployment artifacts (Dockerfile, compose,
entrypoint, healthcheck) are authored and statically validated; the deployment
**application** they package is built and exercised directly over HTTPS via uvicorn,
so the substance of the security gates (HTTPS-only, auth, synthetic enforcement,
headers, egress, packaged E2E) is verified. Container **build/run** gates are reported
as NOT_EXECUTED — never as passed. See `IMPLEMENTATION_DECISIONS.md`.

## P3E does not change governance semantics

P3E is a deployment/operational-hardening phase. It adds a separate
`governance_studio_deployment` package that wraps the frozen backend (`create_app`)
and the frozen frontend build. No ranking/composition/eligibility/replay/comparison/
fallback/permission-proposal/what-if behavior, and no OpenAPI/AWC/compiler source, is
modified.
