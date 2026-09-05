# Ugence approver identity adapter (AI-C) — scoping record

**Status: SCOPED, RULED AND IMPLEMENTED** as `packages/integration/approver-identity-jwt`
0.1.0 `[V]`, labelled `REFERENCE_GRADE_SHADOW_ONLY`; real enterprise-issuer validation
remains unproven. This record scopes step
AI-C of `ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md`: the first real implementation of
`ApproverIdentityPort` (AI-A, `governed-review-service` 0.3.0). The five decisions in
§5 were ruled by the owner on 2026-09-05, in the AI-C implementation instruction; the
ruling commit that instruction cites (`14a20cdc`) was not found on the remote, so the
rulings are recorded here from the instruction's text `[V]`. Rulings ID-1 to ID-5
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
| `authenticated_at` | `auth_time`, else `iat` (required) | which one was used is recorded on the adapter's answer, never invented; `iat` is required, so a token with neither is refused |
| `expires_at` | `exp` | required; the service compares it to the injected clock at the write (row 6) |
| `tenant_claims` | one configured claim name | string → one claim; array → as many as listed; absent → empty; the service applies ID-4 |
| `acr`, `amr` | `acr`, `amr` | as asserted; empty when absent (ID-5) |
| `proof_id_digest` | `sha256(jti)` | only when `jti` is present |
| `actor_type` | one configured claim name and one configured HUMAN value | `HUMAN` iff the claim is present and equals the configured value exactly; missing, different or unknown is `SYSTEM` (row 5); never inferred from `sub`, `client_id`, `amr` or `auth_time` (IA-4) |
| `nbf` | `nbf`, when present | checked by the adapter against the injected clock at authentication; the port carries no not-before, so the service cannot re-check it at the write (`[G]`, §4) |

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

## 5 — Owner decisions (ruled 2026-09-05)

| # | Ruling |
|---|---|
| **IA-1** | **`JWT_LOCAL_VALIDATION`.** The proof is a signed RFC 9068 `at+jwt` access token validated locally against the issuer's published keys. No introspection round trip and no client credential in the review service. |
| **IA-2** | **`PYJWT_OVER_CRYPTOGRAPHY`.** `PyJWT[crypto]` over the ratified `cryptography` backend, both pinned with lower and upper bounds. `alg` allowlist RS256, ES256 and EdDSA; HMAC, `none`, malformed tokens, wrong issuer or audience, unknown keys and oversized proofs are refused. |
| **IA-3** | **`CONFIGURED_JWKS_NO_DISCOVERY`.** Issuer, review-service audience and JWKS URL are explicit configuration. Keys are cached by `kid`, refreshed once on an unknown `kid`, then fail closed. No OIDC discovery; TLS verification is never disabled. |
| **IA-4** | **`EXPLICIT_CLAIM_MAPPING`.** The §3 table as amended: the tenant-claim and actor-type-claim names have no defaults; `HUMAN` requires an exact configured claim and value match, and a missing or unknown actor type is `SYSTEM`; `HUMAN` is never inferred from `sub`, `client_id`, `amr` or `auth_time`; `acr` and `amr` are recorded and no assurance is enforced; `authenticated_at` is `auth_time`, otherwise the required `iat`, and the answer records which supplied it; the adapter reads no wall clock and invents no `nbf` handling beyond the explicit check in §3 against the injected clock. |
| **IA-5** | **`INTEGRATION_PACKAGE_NOW`.** `packages/integration/approver-identity-jwt`, distribution `ugence-approver-identity-jwt`, importing only `ugence_governed_review_service`, `jwt` and the standard library. The port is not promoted; ID-3 stands. |

Recommendations that preceded the rulings are superseded by them; where the ruling
narrows a recommendation (IA-4's HUMAN rule), the ruling governs.

Prohibitions, stated once: no Ugence package becomes an issuer; no HMAC or `none`
algorithms; no credential in the adapter beyond public keys; no import of Decision
Authority, the approval ledger, the directory, the durable engine or the studio; no
clock read; no token in any log, ledger, exception message or answer.

## 6 — Sequence and ceiling

1. **Ruling** on IA-1 to IA-5 (documentation only). Done, above.
2. **AI-C implementation**: the package, its boundary tests, the in-process issuer,
   validation-failure matrix (§4), and the composition seam that wires
   `ReviewService(identity_port=..., tenant_mode=..., production=...)` (fact 9).
   Label: **Reference-grade, shadow-only**. **Shipped `[V]`** except the composition
   seam: no deployment composes the review service, so fact 9 stays open; the
   adapter's README states how a root wires it. `nbf` is checked by the adapter
   against the injected clock and cannot be re-checked by the service (§3, `[G]`).
3. **Issuer validation** against a real enterprise IdP once the owner provisions one
   (fact 10). Until then every `IDP_AUTHENTICATED` label is reference-grade and the
   roadmap's v1 criterion 2 stays unmet.

AI-D (ledger and linkage carry `authentication_reference`) and AI-E (assurance gate)
follow and are unchanged by this record.

## 7 — Next step

AI-D shipped (`ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md` §6). Fact 9, the composition
root, is scoped in `ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md`, awaiting
rulings CR-1 to CR-5. Enterprise-issuer validation of this adapter waits on an
owner-provisioned issuer and is not claimed.
