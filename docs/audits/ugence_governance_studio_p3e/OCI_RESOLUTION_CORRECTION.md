# P3E OCI Resolution — Evidence Correction

## Interpretation correction (§2)

The previous report stated GitHub Actions "was not executing" and implied the GitHub
runner had registry egress blocked. That was **wrong**. Verified from the live Actions
API:

- **GitHub Actions did execute.** Run `30880346449` on the merged default (`7d4fbd46`):
  - `application` job → **success** (all 16 steps: install, p3d-prerequisite,
    openapi/platform freeze, frontend/backend regression, password-hashing-tests,
    python-runtime-audit, frontend-build, synthetic-data-integrity, deployment-suite,
    npm-production-audit). The earlier CI repair works on the real runner.
  - `container` job → **failure at `base-image-digest-verification` (step 5)**, then all
    build/inspect/scan steps **skipped**.
- The container failure was caused by **null `manifest_digest` values in
  `base-images.json`** — a repository-configuration issue — **not** registry egress. The
  step exited before any registry lookup.
- **Registry accessibility from the GitHub runner remains untested** by that run. The
  local development environment's registry-blob denial must not be generalized to the
  GitHub-hosted runner.

Null digests are unresolved **repository configuration**, not an external resource
blockage, and are corrected here.

## Digests resolved and pinned (§3, §6)

The Docker Registry v2 **manifest** API (`auth.docker.io` + `registry-1.docker.io`) is
reachable even in the local environment (only the blob CDN is blocked), so the digests
were resolved and cross-checked:

| Image | Index digest | linux/amd64 child |
|-------|--------------|-------------------|
| `node:22-bookworm-slim` | `sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46` | `sha256:0f65470961851f2354dc8e560853e2f428ea928436135fc7e35780ab100c7e00` |
| `python:3.11-slim-bookworm` | `sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba` | `sha256:28255a3ace7eb4c48bc1b57b90af29e1bc82b4fd6c60614a8e3dce61b87ff941` |

- Committed to `base-images.json` (index + amd64 child + platform + timestamp).
- Every Dockerfile `FROM` pins the **index** digest (`@sha256:…`); buildx selects the
  linux/amd64 child at build time.
- `ci/resolve_base_images.py` performs the resolution (verified locally: both entries
  `resolved`, digests match the committed pins) and is wired as a `workflow_dispatch`
  `resolve-base-images` job that uploads a resolution artifact.
- `base-image-digest-verification` is **blocking**: it re-resolves live, and fails on a
  null pin, a live≠pinned digest, a Dockerfile that does not pin the digest, an
  inaccessible/rate-limited/auth-failed registry, or a platform mismatch.

## Container-gate corrections (§4–§9)

- **TLS (§4):** exact-version via `curl --tls-max 1.0/1.1` (must fail) and `--tlsv1.2`
  (must succeed), plus TLS 1.3 where the client supports it; startup-failure negatives
  (missing cert, missing key, cert/key mismatch, missing credentials, malformed hash)
  each assert the container exits before binding the port.
- **Layer secret scan (§5):** `ci/scan_image_layers.py` `docker save`s the image,
  parses the manifest, and scans the **content** of every layer tar (paths + embedded
  secrets) and the image config — not just the outer archive listing.
- **Runtime hardening (§6):** reads the live container `/proc/1/status`
  (Cap{Eff,Prm,Bnd}=0, NoNewPrivs=1), UID/GID 10001, read-only root, approved tmpfs
  only, no docker socket, only 8443 published.
- **Egress (§7):** separates **enforcement** (`--internal` network → external connect
  refused) from **observation** (records attempted destinations + external DNS result)
  into `runtime-egress-report.json`.
- **E2E (§8):** `ci/packaged_e2e.py` asserts response bodies/state (catalog is exactly
  the four scenarios, `NO_FEASIBLE_TEAM` at HTTP 200, deterministic export, immutable
  what-if baseline) — not HTTP 200 alone — plus auth incl. brute-force cooldown and no
  credentials in logs.
- **Evidence (§9):** SBOM via pinned `anchore/sbom-action@v0.17.9` and scan via pinned
  `aquasecurity/trivy-action@0.28.0` (no unpinned `curl | sh`); an `evidence-manifest.json`
  binds image id, source commit, Dockerfile sha256, base digests, and the SBOM / scan /
  secret-scan / egress artifact hashes.
