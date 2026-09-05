# P3E Container-Completion — Live State

| Item | Value |
|------|-------|
| Live default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default tip | `e496a67978245e57bb9dcbfab2387a3af18781b4` |
| PR #1325 state | open, not merged, not draft |
| PR #1325 base / head | default branch / `claude/governance-studio-p3e-private-hosted` |
| PR #1325 starting head | `8f4faa332016514d9dc2f2fd10c36f03523f5fd3` |
| PR #1323 (P3D) | remains merged |
| Later P3E completion PR exists? | no |
| Working tree at start | clean |

## Branch strategy applied

PR #1325 open and unmerged → corrections pushed to the **same** branch; no second PR.

## Resource gate result

Docker daemon **runs** (started manually; buildx/compose functional; `FROM scratch`
builds succeed). However the organization egress proxy **denies all container-registry
blob CDNs** (Docker Hub `production.cloudfront.docker.com` and GHCR both 403), and
`docker manifest inspect` also fails. **No base image can be pulled and no base digest
resolved.** Per the proxy README, policy denials are reported, not retried/bypassed, and
no `FROM scratch` substitute image was fabricated.

Therefore the container **build/run/scan** gates (C2, C4–C19) remain **NOT_EXECUTED**;
they stay CI-gated for a registry-capable runner. See `CONTAINER_RUNTIME_CAPABILITY.*`.

## Executed this pass (registry-independent)

- **Argon2id** password hardening (`argon2-cffi` from the allowlisted PyPI) — §5 complete.
- **pip-audit** executed (0 known vulns) and **npm audit** (0 critical/high).
- Base-image pinning manifest authored (`base-images.json`, digests UNRESOLVED_EGRESS_DENIED)
  + CI `base-image-digest-verification` job that resolves/verifies where egress permits.
  (Superseded 2026-09-05 by ruling `SEPARATE_PIN_CONFORMANCE_FROM_TAG_DRIFT`: pin
  conformance is network-independent and blocking, mirror-digest conformance is blocking
  when configured and a typed resource blocker when not, upstream tag drift is advisory.)
- Docs/audits corrected to distinguish executed vs NOT_EXECUTED and to record the precise
  egress-policy block. Deployment suite: 93 tests pass.

## Frozen invariants (unchanged)

OpenAPI `dc309eab…` · platform `d993093570…` · synthetic bundle
`c0e5ac73048824f07543f38f67a445cd289ff481f26505c3446bc7609e4dfcdc` · frontend 0.2.0 ·
backend 0.1.0 · contract `governance_studio.api.v1` · AWC 0.2.1 · compiler 0.2.0.
