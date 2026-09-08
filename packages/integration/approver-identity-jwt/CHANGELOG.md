# Changelog — ugence-approver-identity-jwt

## 0.1.0 — 2026-09-05 — AI-C, initial release

Scoped and ruled by `docs/architecture/ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md`
(owner rulings IA-1 to IA-5), implementing step AI-C of
`ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md`. Labelled `REFERENCE_GRADE_SHADOW_ONLY`,
`ISSUER_VALIDATION = "IN_PROCESS_ISSUER_ONLY"`, `ENFORCEMENT_ENABLED = False`.

- `JwtApproverIdentityAdapter` implements the review service's `ApproverIdentityPort`
  over RFC 9068 `at+jwt` access tokens, validated locally against the issuer's
  published keys. The package validates a proof it did not issue: it mints no
  identity, holds no credential beyond public keys, and is not an issuer.
- Asymmetric algorithms only — RS256, ES256 and EdDSA (IA-2). `none`, HMAC, any
  algorithm outside the allowlist, malformed or oversized proofs, wrong `typ`, missing
  `kid`, unknown key after exactly one refresh, foreign or mismatched key, wrong
  issuer, wrong audience, and missing or malformed claims are all refused as
  unauthenticated answers from a closed `Refusal` vocabulary. Verification is never
  relaxed.
- `exp`, `iat` and `nbf` are judged against the **injected clock**; no wall clock is
  read anywhere, asserted over the AST.
- IA-4 claim mapping: the tenant and actor-type claim names have no defaults and the
  two actor fields are set together or not at all; `HUMAN` requires an exact configured
  claim/value match and is never inferred from `sub`, `client_id`, `amr` or
  `auth_time`; `acr`/`amr` are recorded and never enforced; `authenticated_at` is
  `auth_time` else the required `iat`, and the answer records which.
- `keys.py`: `JwksKeyCache` over one configured JWKS URL, stdlib `urllib` with default
  TLS verification, keys cached by `kid`, exactly one refresh for an unknown `kid`,
  then fail closed. Rotation replaces rather than merges. Fetch or parse failures and
  symmetric keys are `KeyRetrievalFailed`, the port's `IdentityUnavailable`; cached
  keys survive an outage.
- `config.py`: `AdapterConfig` requires issuer, audience and JWKS URL explicitly; HTTPS
  only, with a loopback plain-HTTP exception that `production=True` refuses (IA-5).
- No token, on any path, reaches a log record, an answer, a `repr`, an exception
  message or any attribute reachable from the adapter afterwards; the adapter emits no
  log record at all.
- Dependencies are exactly `ugence-governed-review-service`, `PyJWT[crypto]` and
  `cryptography`, the latter two bounded above and below (IA-2); `cryptography` is
  bounded to the range `trusted-evidence-authority` ratified.
- The public API is asserted inline by `tests/test_boundaries.py`
  (`test_public_api_and_honest_labels`), so this package ships no `public_api.json`.
- Contract gap, stated rather than papered over: `VerifiedClaims` carries no
  not-before, so the service cannot re-check `nbf` at the write as it re-checks `exp`.
  The adapter checks `nbf` once, at authentication; the port is not amended here.
- Proven against an in-process issuer only (RSA, EC and Ed25519 keys generated at test
  time, JWKS served on `127.0.0.1`, no egress). Real enterprise-issuer validation
  remains unproven.
- Neighbours unmodified: governed-review-service 0.4.0, governed-review 0.3.0,
  approval-workflow 0.2.0, authority-directory 0.1.0.
