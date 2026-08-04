# Implementation Decisions (P3E)

1. **Separate wrapper package, frozen components untouched.** All P3E code lives in
   `governance_studio_deployment`. The backend is consumed via `create_app()` and the
   frontend via its `dist` build; neither is modified, so no governance semantics and
   no OpenAPI/AWC/compiler source change.

2. **Single-process ASGI.** One Starlette-style dispatcher serves the SPA, the frozen
   API, and `/healthz`/`/readyz` behind one middleware stack (trusted-host → auth →
   origin/header guard → body cap → dispatch), wrapped by security headers. Unknown
   `/api/*` never falls through to the SPA.

3. **HTTP Basic over HTTPS, not an identity platform.** A bounded in-memory failure
   counter with temporary cooldown (no permanent lockout), constant-time credential
   comparison, generic 401s that never disclose username existence, and no credential
   logging. Two modes only: `production` (default) and loopback `test`.

4. **Password KDF = Argon2id** (`argon2-cffi`, installed from the allowlisted PyPI).
   Standard `$argon2id$` encoded format, library-managed salt + constant-time verify,
   bounded cost with excessive-parameter rejection *before* the KDF runs; legacy scrypt
   records are verified for migration only. (Corrects the earlier offline-scrypt fallback.)

5. **Fail-closed startup integrity.** 14 checks (frontend build+version, backend
   version+contract, OpenAPI hash, approved-op manifest, synthetic bundle, fixture
   override guard, TLS validity+expiry, credentials, allowed hosts, dev-in-prod) run
   before binding; on failure the port is never bound and a precise code is emitted.

6. **Synthetic-only, pinned + hashed.** A committed manifest fixes the four scenarios,
   their fixture hashes and an aggregate bundle hash; startup rejects any drift.

7. **No runtime egress.** The container needs no outbound network after build; a test
   guards that a full planning surface issues no non-loopback connection and imports no
   model/agent SDK.

8. **Container execution is environment-gated (honest scope).** This build host has the
   Docker CLI but **no daemon**, so the OCI image cannot be built or run here. The
   container is fully **defined** (multi-stage Dockerfile, non-root 10001, read-only
   root, dropped caps, single port 8443, healthcheck, OCI labels, no secrets) and
   **statically validated** by `tests/test_container_artifacts.py`; build/run and image
   scan are CI-gated and reported **NOT_EXECUTED** here — never as passed.
