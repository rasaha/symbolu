# AP-3 Enterprise Issuer Validation — acceptance report

**Canonical acceptance artifact** for ruling AP-3 (`ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §18, §20, §20.7).
Rendered from `deployment/governed-runtime-worker/AP3_ENTERPRISE_ISSUER_VALIDATION.json` by
`ci/ap3_acceptance_report.py`; the worker's harness fails if this file drifts from the record.
It holds no token, cookie, secret, private key or authorization code.

**Status:** `MET`

**Designated acceptor:** Rakesh Mohan — Founder, Ugence Labs

**Accepted:** Rakesh Mohan — Founder, Ugence Labs (2026-09-11)
**Signed or CI report:** deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md@fb373ce9

## 1 — Designation

| Term | Value |
|---|---|
| Issuer | `https://ugence.cloudflareaccess.com` |
| Audience | `24b3008ed1910d53caebbaffb3358aa801bd9dc5cf9f5af8aa7ada87335b12b3` |
| Validated application hostname | `ap3-validation-endpoint.rakeshmohan888.workers.dev` |
| Planned custom hostname | ap3-validation.ugence.ai (planned; blocked by DNS/zone configuration; not operational; not live-validated) |
| Production-validation scope | human identities authenticated through the designated Google Workspace group ugence-ap3-test@ugence.ai (AP3-D6); Cloudflare service identities are not commissioned for production; their token-shape handling is covered by conformance tests only |
| Designated by / at | Rakesh Mohan / 2026-09-11 |

## 2 — Rulings applied

- **AP3-D1** — Cloudflare token type: a narrowly scoped cloudflare-access adapter profile; AMENDED 2026-09-11 on the live capture: typ absent admitted, typ present must be JWT, alg must be RS256; IA-1 unchanged elsewhere
- **AP3-D2** — Tenant binding: static issuer/audience mapping to tenant ugence.ai, corroborated by the verified email domain, never derived
- **AP3-D3** — Actor-type mapping: explicit claim-shape mapping (human / service token / ambiguous = refuse); type=app decides nothing
- **AP3-D4** — External header boundary: AW-3 preserved; Cf-Access-Jwt-Assertion is transport only, translated by the adapter; production wiring deferred
- **AP3-D5** — Rows 14 to 16: a deterministic test-only WriterAuthorizer may exercise the real adapter and gate; not production AX-5; evidence classification per row below
- **AP3-D6** — 2026-09-11: rows 5, 6, 7 and 13 are satisfied by in-process conformance evidence exercising the real adapter under the cloudflare-access profile, recorded as AP3-D5 records rows 14 to 16; the validated application hostname is ap3-validation-endpoint.rakeshmohan888.workers.dev (ap3-validation.ugence.ai is a planned custom hostname, blocked by DNS/zone configuration, not operational, not live-validated); the present production-validation scope is human identities authenticated through the designated Google Workspace group; Cloudflare service identities are not commissioned for production, their token-shape handling stays covered by conformance tests; ap3_status stays PENDING_VALIDATION pending the owner's acceptance

## 3 — The sixteen rows

| # | Scenario | Required | Result | Evidence class | Executed | Observed |
|---|---|---|---|---|---|---|
| 1 | correct issuer, audience, tenant and human actor | `ACCEPTED` | `ACCEPTED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | ACCEPTED actor=HUMAN tenant=['ugence.ai'] profile=cloudflare-access |
| 2 | wrong issuer | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | REFUSED_ISSUER_MISMATCH |
| 3 | wrong audience | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | REFUSED_AUDIENCE_MISMATCH |
| 4 | wrong tenant | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | REFUSED_EMAIL_DOMAIN_MISMATCH |
| 5 | missing tenant claim | `REFUSED` | `REFUSED` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | in-process conformance evidence over the real adapter under the cloudflare-access profile and the real write gate |
| 6 | workload identity presented as human | `REFUSED` | `REFUSED` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | in-process conformance evidence over the real adapter under the cloudflare-access profile and the real write gate |
| 7 | missing actor-type evidence | `REFUSED` | `REFUSED` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | in-process conformance evidence over the real adapter under the cloudflare-access profile and the real write gate |
| 8 | expired or not-yet-valid token | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | REFUSED_EXPIRED; REFUSED_ISSUED_IN_FUTURE |
| 9 | invalid signature | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | REFUSED_SIGNATURE_INVALID |
| 10 | unknown signing-key id | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | REFUSED_KEY_UNKNOWN |
| 11 | malformed token | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | not-a-token: REFUSED_MALFORMED; two segments: REFUSED_MALFORMED; alg none: REFUSED_ALG_NOT_PERMITTED; alg ES256: REFUSED_ALG_NOT_PERMITTED; typ at+jwt: REFUSED_TYP_NOT_PROFILE_TYPE; kid removed: REFUSED_KID_MISSING |
| 12 | JWKS unavailable with no safely cached key | `REFUSED` | `REFUSED` | `LIVE_CLOUDFLARE_EVIDENCE_REQUIRED` | 2026-09-11 | IDENTITY_UNAVAILABLE (KeyRetrievalFailed) |
| 13 | signing-key rotation | `NEW_VALID_KEY_ACCEPTED_AFTER_CONTROLLED_REFRESH` | `NEW_VALID_KEY_ACCEPTED_AFTER_CONTROLLED_REFRESH` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | in-process conformance evidence over the real adapter under the cloudflare-access profile and the real write gate |
| 14 | valid identity without a directory grant | `AUTHENTICATED_BUT_UNAUTHORIZED` | `AUTHENTICATED_BUT_UNAUTHORIZED` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | 403 REFUSED_UNAUTHORIZED (ruling AX-5, conformance seam), nothing recorded, over both proof channels |
| 15 | valid identity with a wrong-tenant grant | `UNAUTHORIZED` | `UNAUTHORIZED` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | a grant held in another tenant is invisible (403); a gate for another tenant refuses the identity first (REFUSED_TENANT_MISMATCH) |
| 16 | valid identity with the correct scoped grant | `WRITER_AUTHORIZER_PERMITS_ONLY_THE_NAMED_CAPABILITY` | `WRITER_AUTHORIZER_PERMITS_ONLY_THE_NAMED_CAPABILITY` | `IN_PROCESS_CONFORMANCE_SUFFICIENT` | 2026-09-11 | the grant-role grant records the load and does not permit the revoke until the revoke-role grant exists; then the revoke records over Cf-Access-Jwt-Assertion |

## 4 — Live evidence

- JWKS: ci/ap3_jwks_probe.py run by the owner (Rakesh Mohan) on 2026-09-11 from a Windows host with egress, against the designated URL https://ugence.cloudflareaccess.com/cdn-cgi/access/certs; outcome EVIDENCE; two RSA RS256 signing keys published (Cloudflare's current and next key [I]); values transcribed from the owner's terminal output and to be confirmed against a re-run; public key identifiers only, no key material
  - `bd0b1ac89731d202f9f673d391d1aff31282c71a91acd9e15e1ee3cfab40b9eb` (RSA, RS256, sig)
  - `10f9ce4091b745de49aad528f4b59b2104248686527a8c4cae08a65b6ffa599c` (RSA, RS256, sig)
  - document SHA-256 `99668380e52847ea736886e9e7dda09d5ad1a478ea85b4633b330c40cd363305`
- Redacted capture (2026-09-11): alg `RS256`, typ `None`, kid `10f9ce4091b745de49aad528f4b59b2104248686527a8c4cae08a65b6ffa599c`, payload keys `aud`, `country`, `email`, `exp`, `h_INTERNAL_DO_NOT_USE`, `iat`, `identity_nonce`, `iss`, `nbf`, `policy_id`, `sub`, `type`, iss `https://ugence.cloudflareaccess.com`, aud `24b3008ed1910d53caebbaffb3358aa801bd9dc5cf9f5af8aa7ada87335b12b3`, sub non-empty `True`, type `app`.
- Live verification run at 2026-09-11T10:26:39.216350+00:00 by Rakesh Mohan, on the owner's Windows host with egress; output pasted by the owner (not a CI run, not signed): PASS 9, FAIL 0, BLOCKED 4, IN_PROCESS 3; token fingerprint `c6ba7d44bb2eaa5093426c290f8e8fcfc9aa886538aaf078043abce16307661b`; never displayed (the login line was suppressed by the tool), never retained.
- Exposed token `sha256:cda7677fef4fcf2a791267e7117991c993ff1ac1362daeb1d484f3e1665f9a22`: revocation attested by Rakesh Mohan on 2026-09-11; status `REVOKED_AND_EVIDENCED`; evidence: {'source': "Cloudflare Zero Trust > Insights & Logs > Logs > Admin activity logs (account ffb4142d…c299), as displayed to the owner on 2026-09-11 and transcribed from the owner's screenshot", 'entries': [{'event': 'Revoke application tokens', 'product': 'Access', 'resource': 'Access', 'actor': 'rakeshmohan888@gmail.com', 'displayed': 'September 11, 2026 03:32 PM IST', 'utc': '2026-09-11T10:02Z (minute precision, as displayed)', 'meaning': "the first revocation: after the exposure (the redacted capture preceded the 15:27 IST application update) and before the verifier's fresh token was issued at 15:56 IST; the exposed token (sha256 cda7677f…9a22) was revoked at the Access edge from this instant"}, {'event': 'Revoke application tokens', 'product': 'Access', 'resource': 'Access', 'actor': 'rakeshmohan888@gmail.com', 'displayed': 'September 11, 2026 04:58 PM IST', 'utc': '2026-09-11T11:28Z (minute precision, as displayed)', 'meaning': "a second revocation performed by the owner while producing this evidence; it also revokes the verifier run's token (sha256 c6ba7d44…661b), which is never used again"}, {'event': 'Update application policy', 'product': 'Access', 'displayed': 'September 11, 2026 03:27 PM IST', 'meaning': 'the account-audit-log PUT event 01a08fe6… reviewed earlier: a policy update, not the revocation'}], 'dashboard_confirmation': "the application page showed 'Tokens successfully revoked' on the second revocation (owner screenshot, 2026-09-11)"}.

## 5 — Remaining owner actions


## 6 — Acceptance

Accepted by Rakesh Mohan — Founder, Ugence Labs (2026-09-11). Report reference: `deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md@fb373ce9`.

Statement as issued:

> I, Rakesh Mohan, Founder, Ugence Labs, accept the AP-3 Enterprise Issuer Validation for the Cloudflare Access issuer https://ugence.cloudflareaccess.com, audience 24b3008ed1910d53caebbaffb3358aa801bd9dc5cf9f5af8aa7ada87335b12b3, validated on the application hostname ap3-validation-endpoint.rakeshmohan888.workers.dev, scoped to human identities authenticated through the designated Google Workspace group, on the basis of deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md at commit fb373ce9: rows 1 to 4 and 8 to 12 by my live cryptographic run of 2026-09-11, rows 5 to 7 and 13 under AP3-D6 and rows 14 to 16 under AP3-D5 by in-process conformance evidence. The exposed token is revoked and evidenced. Set ci_run_or_signed_report to deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md@fb373ce9, set accepting_owner to "Rakesh Mohan — Founder, Ugence Labs (2026-09-11)", move ap3_status to MET, re-render the report, update draft PR #1748, and do not merge.

