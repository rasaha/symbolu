# Ugence approver identity adapter (AI-C) — scoping record

**Status: SCOPED, AWAITING RULING — nothing here is implemented.** This record scopes
step AI-C of `ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md`: the first real implementation
of `ApproverIdentityPort` (AI-A, `governed-review-service` 0.3.0). It authorizes no
code, adds no dependency and integrates no identity provider. Rulings ID-1 to ID-5
stand and are not reopened.

Evidence labels: `[V]` verified against this repository at the merge of PR #1631,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

**Can a real adapter validate an IdP-issued proof, fill `VerifiedClaims` exactly, and
be proven in CI that has no egress, without any Ugence package becoming an identity
provider?** Yes, under five rulings: the proof is a signed JWT access token validated
locally against the issuer's published keys; the validation library is PyJWT over the
repository's already-ratified `cryptography` backend; keys come from a configured JWKS
URL, cached, fail-closed, with no runtime discovery; claims map onto `VerifiedClaims`
by one configured table; and the adapter is its own integration-layer package whose
boundary tests forbid every Ugence package but `governed-review-service`.

## 2 — What exists

| # | Fact | Label |
|---|---|---|
| 1 | The port and shape exist: `ApproverIdentityPort.authenticate(proof) -> ApproverIdentity`, `VerifiedClaims(issuer, subject, audience, authenticated_at, expires_at, tenant_claims, acr, amr, proof_id_digest)`, `IDP_AUTHENTICATED` reserved for a real adapter, `StaticApproverIdentityAdapter` refused in production (`governed-review-service/.../identity.py`). The service, not the adapter, binds subject, checks expiry at the write, derives tenant and records assurance. | `[V]` |
| 2 | The relay exists: the studio forwards `X-Ugence-Approver-Proof` on the decision route only, unread (`clients/review.py`, `PROOF_ROUTE`); the review service reads it in `http.py`. | `[V]` |
| 3 | No JWT, JOSE or OIDC library is declared by any package; `governed-review-service`'s boundary test forbids `jwt`, `authlib`, `msal`, `oauthlib`, `ldap3` and the source tokens `oidc`, `jwt`, `bearer` (`tests/test_boundaries.py`). The adapter therefore cannot live inside the service. | `[V]` |
| 4 | `cryptography` is the repository's ratified cryptographic backend: `trusted-evidence-authority` depends on `cryptography>=41.0.7,<47.0.0` after an in-package Ed25519 was audited and deleted; `package-suites-ci.yml` installs it and calls a pure-Python fallback a downgrade to be refused. | `[V]` |
| 5 | CI reaches PyPI (every workflow runs `pip install`) but the organisation's egress blocks registry blob CDNs (P3E); no workflow reaches an external issuer. Tests already stand a real `http.server` up on `127.0.0.1` for what goes over the wire (`test_review_relay.py`, `test_review_proof_relay.py`). | `[V]` |
| 6 | Layering: `packages/integration/*` may import other integration packages; capabilities and leaves may not (`scripts/check_package_import_boundaries.py`). An adapter importing `ugence_governed_review_service` must therefore be an integration package. | `[V]` |
| 7 | The directory never reads claims: group-claim ingestion is rejected (directory ADR D-4) and it returns no `ActorType`. Eligibility stays string-equality on `decided_by` (row 3). | `[V]` |
| 8 | Every Ugence package reads no clock; instants are injected. PyJWT checks `exp`/`nbf` against `time.time()` unless told not to. | `[V]` / `[I]` |
| 9 | No composition root wires `ReviewService` with an identity port: `build_app(service)` is the only entry, and no deployment composes the review service. | `[G]` |
| 10 | No enterprise IdP, test tenant or issuer is provisioned anywhere. | `[G]` |

## 3 — Claim mapping onto `VerifiedClaims` `[I]`

| Field | Source | Rule |
|---|---|---|
| `issuer` | `iss` | must equal the configured issuer exactly |
| `subject` | `sub` | required; `decided_by` becomes `subject_reference(iss, sub)` (ID-2) |
| `audience` | `aud` | must contain the configured review-service audience; a studio-audience token is refused unauthenticated (row 14) |
| `authenticated_at` | `auth_time`, else `iat` | which one was used is recorded on the adapter's answer, never invented |
| `expires_at` | `exp` | required; the service compares it to the injected clock at the write (row 6) |
| `tenant_claims` | one configured claim name | string → one claim; array → as many as listed; absent → empty; the service applies ID-4 |
| `acr`, `amr` | `acr`, `amr` | as asserted; empty when absent (ID-5) |
| `proof_id_digest` | `sha256(jti)` | only when `jti` is present |
| `actor_type` | rule under IA-4 | `HUMAN` only when the token carries a human sign-in; a client-credentials token is `SYSTEM` (row 5) |

Signature, `alg` allowlist, `iss`, `aud`, structural validity and key lookup are the
adapter's; everything after that is the service's and already tested (AI-A).

## 4 — Failure surface the adapter must own `[I]`

| Failure | Answer |
|---|---|
| malformed token, bad signature, unknown `kid`, `alg` outside the allowlist (`none`, HMAC), wrong `iss`, `aud` without the service | `authenticated=False` (row 1); never an exception |
| JWKS unreachable, TLS failure, malformed JWKS, cache empty and refresh failed | `IdentityUnavailable` (row 7, fail closed) |
| token above a size ceiling | unauthenticated, before any parse |
| key rotation | cache keyed by `kid`; one refresh on unknown `kid`; unknown after refresh is unauthenticated |
| test issuer in CI | an in-process `http.server` on `127.0.0.1` serving a JWKS whose key `cryptography` generated at test time; tokens signed in-test; no egress |

The adapter never logs, stores or returns the token, never reads a clock, and never
answers eligibility or tenant policy. Against the in-process issuer its label is
`IDP_AUTHENTICATED` at **reference-grade**; against a real enterprise issuer it is
unverified until fact 10 is closed.

## 5 — Owner decisions `[R]`

| # | Decision | Recommendation |
|---|---|---|
| **IA-1** | Proof format: a signed JWT access token (RFC 9068 `at+jwt`) validated locally, or an opaque token introspected at the issuer per decision (RFC 7662). | **JWT, local validation.** Introspection needs a client credential in the review service and a round trip per decision; local validation needs only public keys. |
| **IA-2** | Validation library: `PyJWT[crypto]` over `cryptography`; `authlib`; `python-jose`. | **PyJWT over `cryptography`**, pinned with lower and upper bounds as TEV pins `cryptography`; the crypto backend is already ratified and installed in CI. `alg` allowlist RS256, ES256, EdDSA. |
| **IA-3** | Key retrieval: a configured issuer and JWKS URL, cached, fail-closed, no discovery; or OIDC discovery at runtime. | **Configured JWKS URL, no discovery.** Discovery adds a second unauthenticated fetch and a second thing to pin. Stdlib `urllib` only, as the studio client does; TLS verification never disabled. |
| **IA-4** | Claim mapping table (§3): the tenant claim name, the `auth_time`→`iat` fallback, and the HUMAN rule. | Tenant claim name is configuration with no default (an unconfigured name records no tenant); `auth_time` else `iat`, recorded; HUMAN iff `sub` differs from `client_id` and `amr` or `auth_time` is present, else SYSTEM. |
| **IA-5** | Package placement: `packages/integration/approver-identity-jwt` importing only `ugence_governed_review_service`, `jwt`, stdlib; or promote the port to governance-contracts first. | **Integration package now; no promotion.** ID-3 keeps the port service-local until a second real consumer; the adapter is a consumer of the port, not a second port. |

Prohibitions, stated once: no Ugence package becomes an issuer; no HMAC or `none`
algorithms; no credential in the adapter beyond public keys; no import of Decision
Authority, the approval ledger, the directory, the durable engine or the studio; no
clock read; no token in any log, ledger, exception message or answer.

## 6 — Sequence and ceiling

1. **Ruling** on IA-1 to IA-5 (documentation only).
2. **AI-C implementation**: the package, its boundary tests, the in-process issuer,
   validation-failure matrix (§4), and the composition seam that wires
   `ReviewService(identity_port=..., tenant_mode=..., production=...)` (fact 9).
   Label: **Reference-grade, shadow-only**.
3. **Issuer validation** against a real enterprise IdP once the owner provisions one
   (fact 10). Until then every `IDP_AUTHENTICATED` label is reference-grade and the
   roadmap's v1 criterion 2 stays unmet.

AI-D (ledger and linkage carry `authentication_reference`) and AI-E (assurance gate)
follow and are unchanged by this record.

## 7 — Next step

Rule on IA-1 to IA-5. No implementation prompt is issued while they are open.
