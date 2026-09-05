# Ugence Approver Identity JWT

**A locally validated RFC 9068 access token as proof of who decided.** The first real
implementation of the governed review service's `ApproverIdentityPort` (AI-C, owner
rulings IA-1 to IA-5, `docs/architecture/ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md`).

    THIS PACKAGE VALIDATES A PROOF IT DID NOT ISSUE. IT MINTS NO IDENTITY, HOLDS NO
    CREDENTIAL BEYOND PUBLIC KEYS, AND NEVER LOGS, STORES OR RETURNS A TOKEN.

## Maturity — read this before citing the package

`REFERENCE_GRADE_SHADOW_ONLY`, `ISSUER_VALIDATION = "IN_PROCESS_ISSUER_ONLY"`,
`ENFORCEMENT_ENABLED = False`. Signatures are verified with the ratified `cryptography`
backend through PyJWT, but the only issuer this adapter has ever been run against is
the in-process test issuer in its own suite. **Validation against a real enterprise
identity provider is unproven.** A decision it authenticates is labelled
`IDP_AUTHENTICATED` by the review service at reference grade; the roadmap's v1
criterion 2 stays unmet until an owner-provisioned issuer exists. Nothing is
pilot-validated or production-certified.

## What it does

`JwtApproverIdentityAdapter(config, clock=...)` implements
`authenticate(proof) -> JwtApproverIdentity`, the port's answer plus two fields the
rulings oblige it to record: `authenticated_at_source` (`auth_time` or `iat`) and, when
unauthenticated, `refusal`, one of a closed vocabulary (`Refusal`).

Accepted, in order (IA-1, IA-2, IA-3):

1. a string no larger than `max_proof_bytes` (refused before any parse);
2. a JWT header naming `alg` in `RS256`, `ES256`, `EdDSA` (HMAC and `none` refused
   from the header, no key fetched), `typ` `at+jwt` or `application/at+jwt`, and a
   `kid`;
3. a key for that `kid` from the configured JWKS URL: cached, refreshed exactly once
   for an unknown `kid`, then `KEY_UNKNOWN`; a JWKS that cannot be fetched or parsed,
   or that carries a symmetric key, is `KeyRetrievalFailed`, the port's
   `IdentityUnavailable`, so the service fails closed (row 7). No discovery document
   is ever fetched; TLS verification is the standard library's default and is never
   relaxed; plain HTTP is accepted only for a loopback host outside production;
4. a signature that verifies under that key, `iss` equal to the configured issuer,
   `aud` naming the configured review-service audience (a studio-audience token is
   refused, row 14), and `iss`, `sub`, `aud`, `exp`, `iat` present;
5. against the **injected clock** and never the wall clock: `exp` in the future,
   `iat` not in the future, and `nbf`, when present, already reached.

Mapped, exactly as ruled (IA-4):

| `VerifiedClaims` field | Source |
|---|---|
| `issuer`, `subject`, `audience` | `iss`, `sub`, the configured audience |
| `authenticated_at` | `auth_time`, else `iat`; the answer records which |
| `expires_at` | `exp` (the service re-checks it at the write, row 6) |
| `tenant_claims` | the configured `tenant_claim`, string or list, as presented; unconfigured records none |
| `acr`, `amr` | as asserted, empty when absent; no level is enforced (ID-5) |
| `proof_id_digest` | `sha256(jti)` when `jti` is present |
| `actor_type` | `HUMAN` iff the configured `actor_type_claim` equals the configured `human_actor_type_value` exactly; otherwise `SYSTEM`; never inferred from `sub`, `client_id`, `amr` or `auth_time` |

Everything after that is the review service's: subject binding (row 2), expiry at the
write (row 6), tenant policy (ID-4), eligibility (row 3), replay (row 8).

**Contract gap, stated rather than papered over `[G]`.** `VerifiedClaims` carries no
not-before, so the service cannot re-check `nbf` at the write as it re-checks `exp`.
The adapter checks `nbf` once, at authentication, against its injected clock; the port
is not amended by this package.

## Configuration

`AdapterConfig(issuer, audience, jwks_url, tenant_claim=None, actor_type_claim=None,
human_actor_type_value=None, max_proof_bytes=8192, fetch_timeout_s=5.0,
production=False)`. The first three are required and have no defaults; the claim
names have no defaults and the two actor fields are set together or not at all. With
`production=True` a loopback or plain-HTTP JWKS URL is refused.

No composition root in this repository wires the adapter yet (adapter ADR fact 9): a
deployment constructs `ReviewService(identity_port=JwtApproverIdentityAdapter(...),
tenant_mode=..., production=...)` in its own root.

## Evidence

`tests/_issuer.py` — an in-process issuer: RSA, EC and Ed25519 keys generated at test
time with `cryptography`, a JWKS served on `127.0.0.1` only, tokens signed in-test. It
is a test fixture; no Ugence package is an issuer.

`tests/test_failure_matrix.py` — the adapter ADR's §4 surface: every permitted
algorithm accepted; malformed, oversized, `none`, HMAC, non-allowlisted, wrong type,
missing `kid`, unknown `kid` after exactly one refresh, foreign key, wrong key type,
wrong issuer, wrong or studio audience, missing and malformed claims; cache hits,
rotation with replace-not-merge, outages as `IdentityUnavailable` with cached keys
surviving; expiry, issued-in-future and not-before by the injected clock, and the wall
clock playing no part; configuration refusals.

`tests/test_claim_mapping.py` — IA-4 exactly: tenant as presented, malformed refused,
unconfigured never recorded; HUMAN only on the exact configured match, never inferred
from `sub`, `client_id`, `amr` or `auth_time`; `acr`/`amr` recorded and never
enforced; `auth_time` else `iat` with the source recorded; the references follow from
the claims, not the token.

`tests/test_redaction.py` — no fragment of any token, on any path, appears in an
answer, a repr, a log record, an exception message or any attribute reachable from
the adapter afterwards; the adapter emits no log record at all.

`tests/test_end_to_end.py` — behind the real `ReviewService` over the real SQLite
ledger: a signed proof records an `IDP_AUTHENTICATED` decision with its
`authentication_reference`; rows 1, 2, 5, 6, 7 and 14 hold with the adapter in the
seam; the token reaches neither the ledger, the runtime signal nor the outcome.

`tests/test_boundaries.py` — imports are the review service, PyJWT and stdlib only;
no clock; asymmetric algorithms only; verification never relaxed; no discovery, no
introspection, no logging, no private key material, no issuer; bounded dependencies;
the public API and its honest labels.

## Dependencies

`ugence-governed-review-service`, `PyJWT[crypto]` (bounded), `cryptography` (bounded to
the range `trusted-evidence-authority` ratified). Nothing else: no Decision Authority,
approval ledger, directory, durable engine, studio or HTTP client library.

## Known gaps `[G]`

- Unvalidated against a real enterprise issuer; no issuer, test tenant or key
  rotation policy is provisioned.
- No composition root wires the adapter into a running review service.
- `nbf` is checked only at authentication (above).
- The approval record and the linkage carry no `authentication_reference` (AI-D); no
  assurance policy or gate exists (AI-E).
