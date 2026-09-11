# Changelog — ugence-approver-identity-jwt

## 0.1.4 — 2026-09-11 — `ISSUER_VALIDATION` moved off `IN_PROCESS_ISSUER_ONLY`

Label only: no source path, claim mapping or refusal changes. `MATURITY` stays
`REFERENCE_GRADE_SHADOW_ONLY` and `ENFORCEMENT_ENABLED` stays `False`.

- `ISSUER_VALIDATION` is now `CLOUDFLARE_ACCESS_HUMAN_WORKSPACE_GROUP_NONPROD_VALIDATED_2026_09_11_AP3_D6`,
  because the owner accepted the AP-3 record on 2026-09-11
  (`deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md@fb373ce9`). Every token
  of the label is a scope limit: Cloudflare Access; human identities authenticated
  through the designated Google Workspace group; a non-production application; the
  acceptance date; ruling AP3-D6. Service identities are not commissioned. It is not a
  production certification and says so by omission.
- New `ISSUER_VALIDATION_SCOPE`: the same facts as fields, including
  `production_certified: False`, the record and report paths and the acceptor.
- `tests/test_boundaries.py` pins the label's shape, the scope fields and the absence of
  any production claim.

## 0.1.3 — 2026-09-11 — AP3-D1 amended on live evidence

The owner's redacted capture of a live Cloudflare Access token (2026-09-11) showed a
header with `alg` and `kid` and **no `typ`**. AP3-D1 was amended the same day, narrowly,
and this release applies it. Nothing changes for the `rfc9068` profile; the package
stays `REFERENCE_GRADE_SHADOW_ONLY`, `ISSUER_VALIDATION = "IN_PROCESS_ISSUER_ONLY"`.

- Under `cloudflare-access` only: an absent `typ` is admitted; a present `typ` must be
  exactly `JWT` (`TYP_NOT_PROFILE_TYPE` otherwise); `alg` must be exactly `RS256`
  (`CLOUDFLARE_ALGORITHMS`; `ALG_NOT_PERMITTED` for ES256 or EdDSA under this profile).
- The absence of `typ` relaxes nothing else: `none`, HMAC, a foreign key, a missing or
  unknown `kid`, wrong issuer, wrong audience and every temporal check are refused as
  before, and the suite pins each on the live header shape.
- Export `CLOUDFLARE_ALGORITHMS`.

## 0.1.2 — 2026-09-11 — the Cloudflare Access issuer profile (AP3-D1 to AP3-D3)

One narrowly scoped issuer profile, selected only by explicit configuration; the
`rfc9068` default and every other issuer are unchanged. The package stays
`REFERENCE_GRADE_SHADOW_ONLY`, `ISSUER_VALIDATION = "IN_PROCESS_ISSUER_ONLY"`: the
profile is conformance-tested against the in-process issuer only, and AP-3 is not met.

- `AdapterConfig.issuer_profile` (`rfc9068` | `cloudflare-access`), `bound_tenant`,
  `verified_email_domain`. The Cloudflare profile requires an issuer of exactly
  `https://<team>.cloudflareaccess.com`, that team's `/cdn-cgi/access/certs` as the
  JWKS URL (loopback outside production only), both binding fields, and none of the
  IA-4 claim-name fields.
- AP3-D1: under the profile the header `typ` must be exactly `JWT`; anything else,
  including `at+jwt`, is the new `Refusal.TYP_NOT_PROFILE_TYPE`. IA-1 is unchanged
  for the `rfc9068` profile.
- AP3-D2: the tenant is the configured static binding, selected by the verified
  issuer-and-audience pair and corroborated by the verified email's domain (NFC,
  trimmed, domain case-insensitive); `Refusal.EMAIL_DOMAIN_MISMATCH` otherwise.
- AP3-D3: the ratified claim-shape mapping; `Refusal.ACTOR_SHAPE_AMBIGUOUS` for any
  mixed or incomplete shape; `type: app` is never read; `sub` is not required at
  decode time under the profile (`CLOUDFLARE_REQUIRED_CLAIMS`) because the shape
  mapping decides what its absence means.
- `JwtApproverIdentity.issuer_profile` records which profile judged the proof.
- Exports: `ISSUER_PROFILES`, `RFC9068_PROFILE`, `CLOUDFLARE_ACCESS_PROFILE`,
  `CLOUDFLARE_ACCESS_TOKEN_TYPE`, `CLOUDFLARE_REQUIRED_CLAIMS`. `Refusal` grows from
  14 to 17 members. `tests/test_cloudflare_access_profile.py` is the profile's suite.

## 0.1.1 — 2026-09-08 — declared floor corrected

Metadata only: no source, claim-mapping or behaviour change; the package stays
`REFERENCE_GRADE_SHADOW_ONLY`, `ISSUER_VALIDATION = "IN_PROCESS_ISSUER_ONLY"`.

- `ugence-governed-review-service` floor raised `>=0.3.0` -> `>=0.6.1`. 0.3.0 defines
  the port (AI-A) but drops the reference this adapter exists to supply; 0.4.0 records
  it (AI-D); and every service release before 0.6.1 declares floors that resolve a
  `governed-review` or `approval-workflow` without the field. 0.6.1 is therefore the
  first release whose own metadata resolves what this adapter needs.
- `tests/test_boundaries.py` now pins the floor itself, so lowering it fails the suite.

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
