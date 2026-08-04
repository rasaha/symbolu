# Security Assumptions (P3E)

- **Single tenant, single instance.** One operator credential; not an identity platform.
- **Synthetic data only.** No production/customer/enterprise data; the bundle is pinned and hashed, fail-closed.
- **HTTPS terminates at the app.** Operator provides certificate material out-of-band; the private key is mounted read-only and never baked into the image.
- **Trusted proxy is opt-in.** Forwarded client addresses are trusted only when `UGENCE_STUDIO_TRUSTED_PROXY=1`.
- **No authorization semantics.** The app proposes; it never grants permissions, provisions credentials, authorizes business actions, or executes agents.
- **Host compromise is out of scope.** We do not claim protection against a compromised host administrator (see THREAT_MODEL).
- **Password KDF.** Argon2id is preferred; this offline build uses stdlib `scrypt` (memory-hard) with a constant-time verifier. The hash format is self-describing to allow an additive Argon2id migration.
- **CSP is strict** (`'self'`, no `unsafe-eval`/`unsafe-inline`/wildcards); the frozen SPA build is compatible with it.
