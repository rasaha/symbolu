# P3E CI Repair — Evidence

PR #1325 merged while its CI was failing. This hotfix pass repairs the workflows and
completes the container gate definitions. Failures were **reproduced locally** before
fixing.

## 1. P3E application job — `ModuleNotFoundError: No module named 'argon2'`

**Cause:** the workflow installed the backend/AWC/compiler but never installed
`deployment/governance-studio`, whose `pyproject.toml` declares `argon2-cffi`.

**Reproduced** (clean venv, old install order): `import argon2` → `ModuleNotFoundError`.

**Fix:** install every local package — including the deployment package — in **one**
resolver transaction:

```
pip install -e packages/tooling/policy-workflow-compiler \
            -e packages/capabilities/agent-workforce-composer \
            -e apps/ugence-governance-studio/backend \
            -e deployment/governance-studio
```

**Verified** (fixed venv): `import argon2, governance_studio_deployment` OK; AWC 0.2.1;
deployment suite **96 passed**, password tests **10 passed**, backend **142 passed**.
The install step asserts the imports so a missing dependency fails the job immediately.

## 2. P3C / P3D integration jobs — AWC `ResolutionImpossible`

**Cause:** the backend (which requires the local `ugence-agent-workforce-composer`) was
installed **before** AWC was a resolvable local distribution; pip then sought AWC on PyPI.

**Reproduced** (clean venv, old order): `ERROR: ResolutionImpossible … ugence-governance-studio-api==0.1.0`.

**Fix:** install the compiler + AWC editables in the **same** `pip install` transaction as
the backend. **Verified:** backend + AWC resolve (`AWC 0.2.1`).

## 3. Security gates

- Removed the `pip-audit … || true` on the security gate; `python-runtime-audit` runs
  `pip-audit` blocking (executed: **0 known vulnerabilities**).
- `npm-production-audit` now parses `--json` and asserts 0 critical/high, printing exact
  moderate/low counts — never describing a result with findings as "clean".

## 4. Container gates — placeholders replaced, base-image job made blocking

- `base-image-digest-verification` now **fails** on any null/unresolved digest, a
  Dockerfile that does not pin the digest, a live≠pinned digest, or an unverifiable
  platform — it no longer prints "RESOLVED" and continues.
- The `echo` placeholders are replaced with executable, blocking steps: `container-build`
  (buildx, metadata capture), `image-inspection` (user 10001, only 8443/tcp, no
  npm/node/compiler), `runtime-package-inventory`, `image-secret-history-scan` (history +
  `docker save` layer scan), `container-runtime-verification`
  (`ci/verify_container.sh`: UID/GID 10001, CapEff 0, NoNewPrivs 1, read-only root,
  TLS 1.0/1.1 rejected, auth 401/200, **packaged four-scenario E2E over the container
  HTTPS listener** via `ci/packaged_e2e.py`, internal-network no-egress), `image-sbom`
  (Syft, image-bound), `container-vulnerability-scan` (Trivy HIGH/CRITICAL exit-code 1),
  and `clean-checkout-reproducibility`.
- The **packaged E2E driver was smoke-tested locally against a live HTTPS deployment
  server** (all four scenarios, exit 0) — it is genuine and runs identically against the
  container in CI.

## Remaining block (unchanged)

The container job still requires container-registry egress to pull/pin base images. In
this environment the org proxy denies Docker Hub / GHCR blob CDNs (403), so
`base-image-digest-verification` fails closed (digests remain UNRESOLVED_EGRESS_DENIED)
and the build/run/scan gates are `NOT_EXECUTED` here. They execute on a registry-capable
runner. See `CONTAINER_RUNTIME_CAPABILITY.*`.
