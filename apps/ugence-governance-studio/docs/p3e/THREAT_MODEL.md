# Threat Model (P3E)

**Protected assets**: operator credentials, TLS private key, the synthetic bundle
integrity, and the "no execution / no authorization" invariants.

**Trust boundaries**: network↔TLS listener; unauthenticated↔authenticated; browser↔API;
image build↔runtime.

| Threat | Mitigation |
|--------|------------|
| Credential brute force | bounded per-source cooldown + fixed failure delay + generic 401 |
| Credential disclosure | no credential/Authorization logging; hashes only; secrets never in image |
| TLS misconfiguration | TLS 1.2+ enforced; startup fails on missing/invalid/expired cert; no plaintext |
| Host-header attack | trusted-host allowlist; production rejects wildcard |
| Cross-origin abuse | same-origin constraint + deployment request header on mutating requests |
| Stolen browser credentials | short-lived session is browser-managed; no server session store to steal |
| Fixture / bundle tampering | pinned per-fixture + aggregate hashes; fail closed at startup |
| Path / static traversal | StaticFiles confined to the build dir; unknown /api not routed to SPA |
| Sensitive logging | allowlisted structured fields; bodies/queries/credentials dropped |
| Dependency / image compromise | SBOM + blocking npm/py audits + container scan (CI); pinned base digests at release |
| Secret in image layers | `.dockerignore` excludes secrets/keys/.env; secret-scan job |
| Unexpected outbound egress | runtime-egress test; no model/agent SDK imported |
| Internal-operation exposure | 6 internal ops never wired; frontend allowlist enforced |
| Misleading permission/execution semantics | terminology bans; proposals are advisory |

**Accepted / deferred**: a compromised host administrator is **out of scope**;
multi-tenant isolation, SSO/OIDC, WAF/rate-limit-at-edge, and HSM-backed keys are
deferred to later phases.
