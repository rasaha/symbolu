# DilChat API Specification

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Status:** Design phase — this is the API design contract. No server implementation exists.
**Canonical reference:** [`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md). Where this
document and the decision log disagree, the decision log wins and this file is a bug.
**Machine-readable companion:** [`openapi/dilchat.openapi.yaml`](./openapi/dilchat.openapi.yaml)
(OpenAPI 3.1). The hand-authored OpenAPI file and this prose are two views of one contract.

> **Scope of this document.** This specifies the external HTTP contract for the DilChat
> backend: transport, auth, errors, pagination, rate limits, versioning, the full endpoint
> inventory, and worked request/response examples for the flagship flow. It does **not**
> specify internal module wiring, database schema, or the astrology math — those live in
> `DILCHAT_BACKEND_ARCHITECTURE.md`, `DILCHAT_ASTROLOGY_ENGINE_SPEC.md`, and
> `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`.

---

## 1. API principles

### 1.1 Style: REST/JSON over HTTPS

DilChat exposes a **resource-oriented REST API** returning JSON over HTTPS (TLS 1.3, HSTS,
no plaintext). This is deliberate:

- **Mobile-client simplicity (DEC-015).** The primary clients are React Native iOS/Android
  apps. REST maps cleanly to platform HTTP stacks, CDN/edge caching, and offline retry
  queues without a bespoke transport runtime.
- **OpenAPI tooling (DEC-003).** FastAPI emits an OpenAPI 3.1 document natively; the same
  document drives typed client generation, contract tests, mock servers, and this spec's
  lint gate. A single artifact is the source of truth for server, clients, and docs.
- **Auditability.** Every mutation is a discrete, nameable HTTP call — a natural unit for the
  `audit` module and for the consent state machine, where "who did exactly what, when" must
  be reconstructable.

**Rejected:**

- **GraphQL** — a flexible query graph is actively *hostile* to DilChat's core invariant.
  The privacy model (DEC-012/DEC-013) is per-endpoint, scope-gated, and default-deny; a
  general query language widens the authorization surface and makes "never leak the other
  partner's private data" far harder to prove. We want *fewer* ways to ask for data, each
  individually policed.
- **gRPC** — streaming/bidi and codegen ergonomics buy us little for a request/response CRUD
  product, and cost us browser reach (the Next.js account portal, DEC-016), human-debuggable
  payloads, and edge cacheability.

### 1.2 Async job pattern (where REST request/response is the wrong shape)

A few operations are not naturally synchronous — they fan out to the calculation worker pool
or the `arq` broker (DEC-005/DEC-006) and may take seconds to minutes. These use an
**async-job** pattern rather than blocking the request:

| Operation | Why async |
|-----------|-----------|
| `POST /v1/me/export` | Bundles cross-module data into an encrypted archive. |
| `DELETE /v1/me` | Account deletion → `deletion_pending`, finalized by a worker sweep. |
| Versioned recalculation sweeps | Triggered internally when a rule/model version bumps. |

The pattern (see §8): the mutating `POST` returns **`202 Accepted`** with a `Location`
header pointing at a job resource; the client polls `GET …/{job_id}` until
`status: succeeded|failed`. Chart calculation (`POST /v1/charts:calculate`) is a
**synchronous fast-path** — the natal-Moon derivation is cheap enough to return inline (§1.3),
falling back to `202` only under worker-pool saturation.

### 1.3 Conventions

- **Base URL:** `https://api.dilchat.com/v1`. Version is a URI prefix (§5.3).
- **Media type:** `application/json; charset=utf-8` on requests and responses. Problem
  responses use `application/problem+json` (§4).
- **Time:** all timestamps are **UTC, ISO-8601** with a `Z` suffix
  (`2026-08-04T09:30:00Z`). Birth *local* time is carried separately as a civil datetime plus
  an IANA zone (never conflated with the derived UTC instant).
- **Field naming:** **`snake_case`** for all JSON fields and query params. Enum values are
  lowercase `snake_case` unless they name a classical Sanskrit term (e.g. `nakshatra`
  values, `koota` names), which are transliterated lowercase (`ashwini`, `bharani`).
- **IDs:** opaque, prefixed, ULID-backed strings (`usr_…`, `bp_…`, `chart_…`, `cpl_…`,
  `inv_…`, `cg_…`, `agr_…`, `job_…`, `conv_…`, `msg_…`). Clients must treat them as opaque.
- **Booleans / nullability:** absent optional fields are omitted, not `null`, unless `null`
  is semantically distinct from "unset" (documented per field).
- **Method verbs on actions:** state-machine transitions that are not plain CRUD use a
  **colon action suffix** (`POST …/{id}:accept`, `:grant`, `:revoke`, `:approve`,
  `:calculate`, `:preview`, `:unpair`). This keeps side-effecting transitions from being
  mistaken for idempotent `PUT` upserts.

### 1.4 Provenance (invariant)

Every **derived** response body (chart, Guna Milan report, daily profile, climate,
AI output, living-compatibility aggregate) carries a `provenance` block. It is **not**
optional and is the same shape everywhere (schema `Provenance`, DEC-000 canonical tuple):

```json
{
  "provenance": {
    "ephemeris_provider": "swiss",
    "ephemeris_version": "swe-2.10.03",
    "ayanamsa": "lahiri",
    "zodiac": "sidereal",
    "rule_pack_id": "ashtakoota_lahiri_classical_v1",
    "transit_model_version": "dilchat_transit_v1",
    "interpretation_pack_version": "dilchat_interp_v1",
    "interest_model_version": "dilchat_interest_v1",
    "prompt_pack_version": "dilchat_prompts_v1",
    "calc_timestamp": "2026-08-04T09:30:12Z",
    "confidence": 0.98
  }
}
```

Only the fields relevant to a given artifact are populated (a natal chart omits
`interest_model_version`; an AI opener omits `ephemeris_version` unless it consumed astrology
inputs). `confidence` is a 0–1 float; it drops when the Moshier fallback is used (DEC-007) or
when birth time is ambiguous (DEC-017). **AI never recomputes astrology** (DEC-014): AI
endpoints echo the provenance of the deterministic inputs they were handed and stamp their
own `prompt_pack_version`.

---

## 2. Authentication & authorization

### 2.1 Token model (DEC-011)

| Token | Type | Lifetime | Storage | Transport |
|-------|------|----------|---------|-----------|
| **Access token** | JWT, **ES256** (asymmetric), stateless | **10 min** | client memory / secure keystore | `Authorization: Bearer <jwt>` |
| **Refresh token** | Opaque, high-entropy, **rotating** | 30 days sliding | server-side **hashed** as a `Session` row; client stores raw in secure enclave | request body on `/v1/auth/refresh` only |

Access-token claims: `sub` (user id), `sid` (session id), `scp` (granted OAuth-style
scopes, e.g. `["user"]`), `iat`, `exp`, `iss=https://api.dilchat.com`, `aud=dilchat-app`,
`kid` (signing key id for rotation). The **privacy scopes** `PRIVATE_A/PRIVATE_B/SHARED`
are **not** JWT claims — they are resolved server-side per request from the authenticated
`user_id` + the target resource's `couple_id` (DEC-012). A token cannot self-assert couple
membership.

Public JWKS for ES256 verification is served at `GET /v1/.well-known/jwks.json` (unversioned
alias also honored). Key rotation is `kid`-driven; old keys remain published until all live
access tokens expire.

### 2.2 Session lifecycle

```
register ─┐
login ────┼─▶ 200 { access_token, refresh_token, expires_in, session } ──▶ Session row (device-bound)
oidc  ────┤
otp/verify┘

refresh:  POST /v1/auth/refresh { refresh_token }
          ▶ validates hash + session not revoked + not reused
          ▶ ROTATES: old refresh invalidated, new refresh issued, new access issued
          ▶ REUSE DETECTION: a replayed old refresh revokes the whole session family (theft signal)

logout:   POST /v1/auth/logout            ▶ revokes current session (idempotent)
sessions: GET  /v1/auth/sessions          ▶ list active sessions/devices (self only)
          DELETE /v1/auth/sessions/{id}    ▶ revoke a specific session (remote logout)
devices:  GET/POST/DELETE /v1/devices     ▶ push tokens & device registration
```

Refresh **rotation** is mandatory: each successful refresh returns a new refresh token and
atomically invalidates the presented one. Presenting an already-rotated refresh token is
treated as **token theft** and revokes the entire session family (`AUTH_REFRESH_REUSE`).
Logout and **unpairing** both revoke sessions fast — the `Session` rows are the authoritative
revocation surface, which is precisely why refresh tokens are server-side and opaque rather
than self-contained JWTs.

### 2.3 Scope model

Two orthogonal layers:

1. **OAuth-style access scopes** (`scp` claim): coarse capability grants (`user`, and
   internal `admin`/`service` scopes never issued to app clients). MVP app tokens carry
   `user`.
2. **Privacy scopes** (`PRIVATE_A | PRIVATE_B | SHARED`, DEC-012): per-resource,
   policy-based, row-level. Resolved by the **ScopeContext** on every request:
   `(user_id, active_couple_id, resolved_scope)`. **Default deny** — a query without a
   resolved scope is refused by the repository layer, and PostgreSQL RLS is the backstop.

Couple membership is **re-verified on every SHARED request** against the `couples`
membership table; `revoked` membership (post-unpair) denies immediately (DEC-012).
`PRIVATE_A`/`PRIVATE_B` are relative to a couple: the *inviting* member's private scope is
`PRIVATE_A`, the *accepting* member's is `PRIVATE_B`. A user is always `A` or `B` within a
given couple and can only ever reach their own private partition.

### 2.4 Authorization matrix

"Who can call" abbreviations: **self** = the authenticated account acting on its own
resources · **A** = active-couple member A (inviter) · **B** = active-couple member B
(accepter) · **either** = either active member · **both** = requires dual approval from both
members before the effect commits · **public** = no auth.

| Endpoint (representative) | self | A | B | either | both | Notes |
|---|:--:|:--:|:--:|:--:|:--:|---|
| `POST /v1/auth/register`, `/login`, `/refresh`, `/oidc/*`, `/otp/*` | — | — | — | — | — | **public** |
| `POST /v1/auth/logout`, `GET/DELETE /v1/auth/sessions` | ✔ | | | | | own sessions only |
| `GET/PATCH /v1/me`, `/me/preferences`, `POST /me/export`, `DELETE /me` | ✔ | | | | | own account |
| `POST /v1/birth-profiles`, `PATCH`, `GET /me/birth-profile` | ✔ | | | | | private to owner |
| `GET /v1/birth-profiles/{id}` | ✔ | | | | | owner only; **404** for others (§4.3) |
| `POST /v1/charts:calculate`, `GET /v1/charts/{id}` | ✔ | | | | | owner only |
| `POST /v1/guna-milan:preview` | ✔ | | | | | single user, PRIVATE, no couple |
| `GET /v1/couples/{id}/guna-milan` | | | | ✔ | | **SHARED**; membership re-checked |
| `GET /v1/me/daily` | ✔ | | | | | owner's transit profile |
| `GET /v1/couples/{id}/climate` | | | | ✔ | | SHARED |
| `POST /v1/couples/invitations` | ✔ | | | | | any user may invite |
| `POST /v1/couples/invitations/{id}:accept` | ✔ | | | | | accepter must not be inviter |
| `POST /v1/couples/{id}:unpair` | | | | ✔ | | either member; revokes SHARED + sessions scope |
| `POST /v1/consent/grants` (propose) | | | | ✔ | | proposer authors a bounded projection |
| `POST /v1/consent/grants/{id}:grant` | ✔ | | | | | **only the data owner** may grant |
| `POST /v1/consent/grants/{id}:revoke` | ✔ | | | | | grantor may revoke |
| `POST /v1/private/**` | ✔ | | | | | strictly PRIVATE_A **or** PRIVATE_B (own) |
| `POST /v1/couples/{id}/shared/**` | | | | ✔ | | SHARED |
| `POST /v1/couples/{id}/journeys`, steps | | | | ✔ | | SHARED |
| `POST /v1/couples/{id}/agreements` (create/submit) | | | | ✔ | | either may draft |
| `POST /v1/agreements/{id}:approve` / `:reject` | | | | | ✔ | **dual approval** (DEC OQ-8) |
| `POST /v1/ai/*` | ✔ | | | ✔ | | scope depends on inputs supplied (private vs shared) |
| `POST /v1/feedback` | ✔ | | | | | private input |
| `GET /v1/couples/{id}/living-compatibility` | | | | ✔ | | jointly-visible **aggregate only** (OQ-9) |
| `GET /v1/me/audit` | ✔ | | | | | user-visible subset only |

The dual-approval rows are the only endpoints where a single authenticated caller cannot
produce the committed effect: an `Agreement` becomes `active` **only** after both members
`:approve` it (see §7.6). Important agreements are two-party by DEC OQ-8; neutral shared
summaries are one-party author + partner visibility and use the `shared_chat`/journey paths,
not the approval path.

---

## 3. Idempotency

All **unsafe, effectful** `POST`s — anything that creates, charges, pairs, consents, or
approves — accept a client-supplied **`Idempotency-Key`** request header (opaque string,
≤ 255 chars; a UUIDv4 or ULID is recommended).

Applies to (non-exhaustive): `register`, `login`, `otp/verify`, all `:calculate`/`:preview`,
`birth-profiles` create, `couples/invitations` create + `:accept`, `:unpair`, all
`consent/grants` create + `:grant`/`:revoke`, all `agreements` create/`:submit`/`:approve`/
`:reject`, `commitments`/`outcome`, `me/export`, and every `/v1/ai/*` call. Read-only `GET`s
and naturally-idempotent `DELETE`s ignore the header.

**Storage & replay (Redis, DEC-005):**

- On first receipt, the server computes `fingerprint = hash(method, path, user_id, body)`
  and stores `key → {fingerprint, status: in_flight}` in Redis with a **24-hour TTL**.
- On completion, the stored record is updated to `{fingerprint, status, response_snapshot}`
  (status code + body).
- A **replay with the same key + same fingerprint** returns the stored `response_snapshot`
  verbatim (same status, same body) with header `Idempotency-Replayed: true`. The side
  effect happens **exactly once**.
- A replay with the same key but a **different fingerprint** (client reused a key for a
  different payload) fails **`422 IDEMPOTENCY_KEY_REUSED`**.
- A replay while the original is still `in_flight` returns **`409 CONFLICT`** with
  `Retry-After` — the client should back off and retry the poll/read.

Idempotency is layered *under* the consent/pairing state machines: even without a key, those
transitions are guarded by resource state (an already-accepted invitation returns
`INVITATION_USED`, an already-active agreement rejects a second `:approve` from the same
member), so retries are safe. The key makes *network* retries transparent.

---

## 4. Error model

### 4.1 Envelope (`application/problem+json`)

Every non-2xx response is a single, uniform problem object (RFC 9457 flavored):

```json
{
  "type": "https://errors.dilchat.com/scope-denied",
  "title": "Scope denied",
  "status": 403,
  "code": "SCOPE_DENIED",
  "detail": "This resource requires an active couple membership in SHARED scope.",
  "trace_id": "trc_01J9Z8Q2A3B4C5D6E7F8G9H0",
  "errors": [
    { "field": "couple_id", "code": "SCOPE_DENIED", "message": "membership is revoked" }
  ]
}
```

- `type` — stable URI naming the error class (dereferenceable docs page).
- `title` — short, human, stable per `code`.
- `status` — mirrors the HTTP status.
- `code` — **the machine contract**; clients branch on this, never on `title`/`detail`.
- `detail` — human, may be localized; never contains secrets or the existence of another
  partner's private data.
- `trace_id` — correlates to server logs and to the `audit` trail; safe to show users.
- `errors[]` — optional per-field validation breakdown (`{field, code, message}`), present
  for `VALIDATION_*`.

### 4.2 Canonical error codes

| HTTP | `code` | When |
|-----:|--------|------|
| 400 | `VALIDATION_INVALID` | Malformed request (bad JSON, wrong type, unknown enum). |
| 400 | `VALIDATION_MISSING_FIELD` | Required field absent. |
| 400 | `VALIDATION_OUT_OF_RANGE` | Value outside allowed bounds (e.g. `limit > 100`). |
| 401 | `AUTH_TOKEN_MISSING` | No/blank `Authorization` header on a protected route. |
| 401 | `AUTH_TOKEN_INVALID` | Signature/`aud`/`iss` bad, malformed JWT. |
| 401 | `AUTH_TOKEN_EXPIRED` | Access token `exp` passed → client should refresh. |
| 401 | `AUTH_REFRESH_INVALID` | Refresh token unknown/hashed-mismatch/revoked. |
| 401 | `AUTH_REFRESH_REUSE` | Rotated refresh replayed → **session family revoked**. |
| 401 | `AUTH_OTP_INVALID` | OTP wrong or expired. |
| 403 | `SCOPE_DENIED` | Authenticated but scope/policy forbids (SHARED without membership). |
| 403 | `COUPLE_NOT_ACTIVE` | Couple exists but is not `active` (pending/unpaired). |
| 403 | `CONSENT_REQUIRED` | Action needs a granted `ConsentGrant` that is absent. |
| 403 | `DUAL_APPROVAL_REQUIRED` | Effect needs both members' approval; one is missing. |
| 404 | `NOT_FOUND` | Resource absent **or** deliberately masked cross-private (§4.3). |
| 409 | `CONFLICT` | State conflict / idempotency in-flight / version race. |
| 409 | `INVITATION_USED` | Invitation already accepted/consumed. |
| 410 | `INVITATION_EXPIRED` | Invitation past its TTL. |
| 422 | `IDEMPOTENCY_KEY_REUSED` | Same key, different payload fingerprint. |
| 422 | `AI_VALIDATION_FAILED` | AI output failed schema validation → request rejected, retried, or 502'd (§7). |
| 429 | `RATE_LIMITED` | Bucket exhausted; `Retry-After` + `RateLimit-*` headers set. |
| 503 | `EPHEMERIS_UNAVAILABLE` | Calculation worker pool / ephemeris data unavailable. |
| 500 | `INTERNAL` | Unhandled server error (generic; `trace_id` set). |

### 4.3 The cross-private privacy invariant (never leak existence)

Attempting to read **another partner's private resource** — their birth profile, their
private conversation, their private feedback — returns **`404 NOT_FOUND`, never `403`.**
A `403` would confirm the resource *exists*; DilChat's core promise (DEC-013) is that a
partner is **never even told** that the other's private data or private conversation exists.
So:

- Reading `GET /v1/birth-profiles/{id}` for an id you don't own → `404` (indistinguishable
  from a nonexistent id).
- Reading someone else's `private/conversations/{id}` → `404`.
- `SCOPE_DENIED (403)` is reserved for **SHARED** resources where the caller's *lack of
  active membership* is itself not secret (both parties know a couple exists once paired).

This distinction is a tested invariant, not a stylistic choice.

---

## 5. Pagination, rate limits, versioning

### 5.1 Pagination (cursor-based)

List endpoints are **cursor-paginated**, never offset-paginated (stable under concurrent
writes, no deep-page skew):

```
GET /v1/private/conversations?limit=20&cursor=eyJvIjoiMkI...

200 OK
{
  "items": [ ... ],
  "next_cursor": "eyJvIjoiMkI3In0"   // null/absent when no more pages
}
```

- `limit` — default `20`, max `100` (`VALIDATION_OUT_OF_RANGE` above 100).
- `cursor` — opaque, forward-only. Clients pass back `next_cursor` verbatim. A `null` or
  absent `next_cursor` means the last page.
- Default sort is resource-defined and stable (usually `created_at` desc, id tiebreak).

### 5.2 Rate limits

Two independent token buckets, evaluated together; the stricter wins:

- **Per-user** (keyed on `sub`), for authenticated calls.
- **Per-IP** (keyed on client IP), for pre-auth and abuse control.

Responses carry `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` (RFC draft
headers). On exhaustion → **`429 RATE_LIMITED`** with **`Retry-After`** (seconds).

| Endpoint class | Examples | Per-user | Per-IP |
|---|---|---|---|
| **Auth-sensitive** | `login`, `otp/verify`, `refresh` | 10 / 5 min | 30 / 5 min |
| **Write (default)** | profile/couple/consent/agreement mutations | 60 / min | 120 / min |
| **Read (default)** | `GET` resources & lists | 300 / min | 600 / min |
| **Calculation** | `charts:calculate`, `guna-milan:*`, `me/daily`, `climate` | 30 / min | 60 / min |
| **AI** | all `/v1/ai/*` | 20 / min | 40 / min |
| **Export/heavy** | `me/export` | 3 / hour | 10 / hour |

Buckets are Redis counters (DEC-005). Limits are ceilings; exact values are tuned in config,
but the *classes* and the two-bucket model are contract.

### 5.3 Versioning

- **URI version:** `/v1` prefix (this contract). Breaking changes ship under a new prefix
  (`/v2`); additive changes stay in `/v1`.
- **Deprecation:** a sunsetting endpoint returns `Deprecation: true` and a `Sunset:
  <http-date>` header, plus a `Link: <…>; rel="deprecation"` to migration docs. Clients
  should surface/log these.
- **No breaking changes without a version bump.** Adding an optional field or a new enum
  value is additive; removing/renaming a field or tightening validation is breaking.

---

## 6. Endpoint inventory

Legend — **Scope:** `public` · `self` · `SHARED` · `PRIVATE` (owner's private partition) ·
`both` (dual approval). **Idem?** = accepts `Idempotency-Key`. **Mode:** `sync` / `async`
(202 + poll).

### 6.1 `identity`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/auth/register` | Create account (email + Argon2id password) | public | ✔ | sync |
| POST | `/v1/auth/login` | Password login → tokens | public | ✔ | sync |
| POST | `/v1/auth/refresh` | Rotate refresh, mint access | public | ✔ | sync |
| POST | `/v1/auth/logout` | Revoke current session | self | ✔ | sync |
| GET | `/v1/auth/sessions` | List active sessions/devices | self | — | sync |
| DELETE | `/v1/auth/sessions/{id}` | Revoke a session (remote logout) | self | ✔ | sync |
| POST | `/v1/auth/oidc/{provider}` | OIDC login (`apple`,`google`) → tokens | public | ✔ | sync |
| POST | `/v1/auth/otp/request` | Send phone/email OTP | public | ✔ | sync |
| POST | `/v1/auth/otp/verify` | Verify OTP → tokens | public | ✔ | sync |
| GET | `/v1/devices` | List registered devices/push tokens | self | — | sync |
| POST | `/v1/devices` | Register device / push token | self | ✔ | sync |
| DELETE | `/v1/devices/{id}` | Deregister a device | self | ✔ | sync |

### 6.2 `users`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| GET | `/v1/me` | Current profile | self | — | sync |
| PATCH | `/v1/me` | Update profile fields | self | ✔ | sync |
| GET | `/v1/me/preferences` | Notification/locale/display prefs | self | — | sync |
| PATCH | `/v1/me/preferences` | Update prefs | self | ✔ | sync |
| POST | `/v1/me/export` | Start data-export job (DPDP/GDPR) | self | ✔ | **async** |
| GET | `/v1/me/export/{job_id}` | Poll export job | self | — | sync |
| DELETE | `/v1/me` | Request account deletion → `deletion_pending` | self | ✔ | **async** |

### 6.3 `birth_profiles`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/birth-profiles` | Create birth profile (date/time/place) | self/PRIVATE | ✔ | sync |
| GET | `/v1/birth-profiles/{id}` | Fetch a version | self | — | sync |
| PATCH | `/v1/birth-profiles/{id}` | **Creates a new immutable version** | self/PRIVATE | ✔ | sync |
| GET | `/v1/me/birth-profile` | Current (latest-version) profile | self | — | sync |

Birth profiles are **versioned & immutable** (DEC-019 audit posture): `PATCH` does not mutate
in place; it supersedes with a new `version` and a new `id`, preserving history. Exact birth
coordinates are encrypted at rest (OQ-6).

### 6.4 `astrology`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/charts:calculate` | Derive natal chart from a birth profile | self/PRIVATE | ✔ | sync* |
| GET | `/v1/charts/{id}` | Fetch a computed chart | self | — | sync |

Returns natal **Moon** `rashi` / `nakshatra` / `pada` (MVP interpretive basis, OQ-4) plus
ascendant context and full `provenance`. *`sync` fast-path; degrades to `202` + poll only
under worker-pool saturation, and returns `503 EPHEMERIS_UNAVAILABLE` if the pool/ephemeris
is down (DEC-007).

### 6.5 `guna_milan`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/guna-milan:preview` | Single-user preview vs **manually entered** partner data | self/PRIVATE | ✔ | sync |
| GET | `/v1/couples/{couple_id}/guna-milan` | Shared Ashtakoota scorecard for the couple | SHARED | — | sync |

`:preview` supports prospective matches (OQ-3) — **no couple is created**, nothing becomes
shared, partner data stays in the requester's private scope. The shared scorecard requires
active membership. Report schema: 8 Koota components + total (0–36) + trace (§7.4).

### 6.6 `moon_transits`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| GET | `/v1/me/daily?date=YYYY-MM-DD` | Personal daily emotional & interest profile | self | — | sync |
| GET | `/v1/couples/{couple_id}/climate?date=` | Couple daily relational climate | SHARED | — | sync |

`date` defaults to the user's local "today"; boundary is local midnight with next
transition times surfaced (OQ-7). Daily profile carries 12 interest scores (§7.5).

### 6.7 `couples`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/couples/invitations` | Create a pairing invitation (code/link) | self | ✔ | sync |
| GET | `/v1/couples/invitations/{id}` | Inspect invitation status | self | — | sync |
| POST | `/v1/couples/invitations/{id}:accept` | Accept → create active couple | self | ✔ | sync |
| POST | `/v1/couples/{id}:unpair` | Dissolve couple; revoke SHARED + shared sessions | SHARED | ✔ | sync |
| GET | `/v1/couples/{id}` | Couple summary (members, status) | SHARED | — | sync |

Accepter must differ from inviter. Expired invite → `410 INVITATION_EXPIRED`; already
accepted → `409 INVITATION_USED`. Unpair flips membership to `revoked` (DEC-012), which the
scope guard enforces on the very next SHARED request.

### 6.8 `consent`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/consent/grants` | Propose a bounded private→shared projection | either | ✔ | sync |
| POST | `/v1/consent/grants/{id}:grant` | **Owner** authorizes the projection | self(owner) | ✔ | sync |
| POST | `/v1/consent/grants/{id}:revoke` | Grantor revokes a live grant | self(grantor) | ✔ | sync |
| GET | `/v1/consent/grants` | List grants (as grantor/proposer) | either | — | sync |

Consent is the **only** path from private to shared (DEC-013). A grant enumerates exactly
what is projected (a `SharedArtifact` — summary/statement, never the raw message stream). The
partner is never told a private conversation exists (§4.3).

### 6.9 `private_chat`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/private/conversations` | Start a private (single-user) conversation | PRIVATE | ✔ | sync |
| GET | `/v1/private/conversations` | List own private conversations | PRIVATE | — | sync |
| POST | `/v1/private/conversations/{id}/messages` | Post a turn → AI reply | PRIVATE | ✔ | sync |
| GET | `/v1/private/conversations/{id}/messages` | Read message history | PRIVATE | — | sync |

Strictly `PRIVATE_A` **or** `PRIVATE_B` (the caller's own partition). Invisible to the
partner. Cross-private read → `404` (§4.3).

### 6.10 `shared_chat`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/couples/{id}/shared/conversations` | Start a shared conversation | SHARED | ✔ | sync |
| POST | `/v1/couples/{id}/shared/conversations/{cid}/messages` | Post a shared turn | SHARED | ✔ | sync |
| GET | `/v1/couples/{id}/shared/conversations/{cid}/messages` | Read shared history | SHARED | — | sync |

### 6.11 `journeys`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| GET | `/v1/journeys/templates` | List journey templates | self | — | sync |
| POST | `/v1/couples/{id}/journeys` | Instantiate a journey for the couple | SHARED | ✔ | sync |
| GET | `/v1/couples/{id}/journeys/{jid}/steps` | List steps + progress | SHARED | — | sync |
| PATCH | `/v1/couples/{id}/journeys/{jid}/steps/{sid}` | Update step state | SHARED | ✔ | sync |

### 6.12 `agreements`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/couples/{id}/compromise-sessions` | Open a structured compromise session | SHARED | ✔ | sync |
| POST | `/v1/couples/{id}/agreements` | Draft an agreement | SHARED | ✔ | sync |
| POST | `/v1/agreements/{id}:submit` | Move draft → `pending_approval` | SHARED | ✔ | sync |
| POST | `/v1/agreements/{id}:approve` | Member approval (**dual**) | both | ✔ | sync |
| POST | `/v1/agreements/{id}:reject` | Member rejection → back to draft | either | ✔ | sync |
| POST | `/v1/agreements/{id}/commitments` | Attach a commitment to an active agreement | SHARED | ✔ | sync |
| POST | `/v1/agreements/{id}/commitments/{cid}/outcome` | Record commitment outcome | SHARED | ✔ | sync |

`:approve` requires **both** members before the agreement becomes `active` (OQ-8). The second
distinct member's approval is the commit point; a member cannot approve twice.

### 6.13 `ai_guidance`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/ai/explain-component` | Explain a Guna Milan Koota component | either | ✔ | sync |
| POST | `/v1/ai/daily-climate-summary` | Summarize a daily/couple climate | either | ✔ | sync |
| POST | `/v1/ai/conversation-preview` | Preview a hard-conversation approach | PRIVATE | ✔ | sync |
| POST | `/v1/ai/opener` | Suggest conversation openers | either | ✔ | sync |
| POST | `/v1/ai/ffanr` | Facts/Feelings/Assumptions/Needs/Requests decomposition | PRIVATE | ✔ | sync |
| POST | `/v1/ai/compromise-options` | Generate compromise options | SHARED | ✔ | sync |
| POST | `/v1/ai/draft-agreement` | Draft agreement text from inputs | SHARED | ✔ | sync |

**All** AI endpoints (DEC-014): consume only the minimum authorized, deterministically-
computed context; **never** recompute astrology; return **schema-validated structured
output** (`AI_VALIDATION_FAILED` on invalid); echo input provenance + stamp
`prompt_pack_version`; honor safety constraints (DEC-021 — no medical/genetic Nadi, no
inferred infidelity/consent/diagnosis).

### 6.14 `feedback`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| POST | `/v1/feedback` | Submit private feedback/rating input | PRIVATE | ✔ | sync |
| GET | `/v1/couples/{id}/living-compatibility` | Jointly-visible living-compat **aggregate** | SHARED | — | sync |

Private inputs stay private; only the aggregate is jointly visible (OQ-9). Living
Compatibility never feeds back into classical Guna Milan (DEC-019).

### 6.15 `audit`

| Method | Path | Purpose | Scope | Idem? | Mode |
|---|---|---|---|:--:|---|
| GET | `/v1/me/audit` | User-visible subset of the audit trail | self | — | sync |

Returns the user-facing slice (consent grants/revokes, session events, exports, deletions) —
never internal/security events.

---

## 7. Worked examples

Bodies are illustrative but schema-accurate. `Authorization: Bearer <access>` is assumed on
every authenticated call; `Idempotency-Key` shown where relevant.

### 7.1 Register → Login

```http
POST /v1/auth/register
Content-Type: application/json
Idempotency-Key: 01J9ZA0register0key

{ "email": "asha@example.com", "password": "correct-horse-battery-staple", "display_name": "Asha", "locale": "en-IN" }
```
```http
201 Created
Location: /v1/me

{
  "user": { "id": "usr_01J9ZA1", "email": "asha@example.com", "display_name": "Asha", "locale": "en-IN", "created_at": "2026-08-04T09:00:00Z" },
  "tokens": {
    "access_token": "eyJhbGciOiJFUzI1NiIsImtpZCI6ImsyMDI2LTA4In0…",
    "token_type": "Bearer",
    "expires_in": 600,
    "refresh_token": "rt_9f2c…opaque",
    "session": { "id": "ses_01J9ZA2", "device": "ios", "created_at": "2026-08-04T09:00:00Z" }
  }
}
```
```http
POST /v1/auth/login
{ "email": "asha@example.com", "password": "correct-horse-battery-staple" }

200 OK
{ "tokens": { "access_token": "eyJ…", "token_type": "Bearer", "expires_in": 600, "refresh_token": "rt_a71b…", "session": { "id": "ses_01J9ZB1", "device": "ios" } } }
```

### 7.2 Create birth profile → Calculate chart

```http
POST /v1/birth-profiles
Idempotency-Key: 01J9ZC0bp

{
  "birth_date": "1994-03-21",
  "birth_time": "14:30:00",
  "birth_time_known": true,
  "place": { "query": "Jaipur, Rajasthan, India", "latitude": 26.9124, "longitude": 75.7873, "iana_timezone": "Asia/Kolkata" }
}
```
```http
201 Created
{
  "id": "bp_01J9ZC1", "version": 1, "owner_user_id": "usr_01J9ZA1",
  "birth_date": "1994-03-21", "birth_time": "14:30:00", "birth_time_known": true,
  "place": { "display": "Jaipur, Rajasthan, India", "iana_timezone": "Asia/Kolkata", "coordinates_encrypted": true },
  "created_at": "2026-08-04T09:05:00Z"
}
```
```http
POST /v1/charts:calculate
Idempotency-Key: 01J9ZC2calc

{ "birth_profile_id": "bp_01J9ZC1" }
```
```http
200 OK
{
  "id": "chart_01J9ZC3", "birth_profile_id": "bp_01J9ZC1", "birth_profile_version": 1,
  "moon": { "rashi": "vrishabha", "rashi_index": 2, "nakshatra": "rohini", "nakshatra_index": 4, "pada": 3, "longitude_sidereal": 49.7421 },
  "ascendant": { "rashi": "karka", "note": "captured for post-MVP ascendant interpretation (OQ-4)" },
  "tithi": { "index": 12, "name": "dwadashi", "paksha": "shukla", "note": "stored, not scored in MVP (OQ-5)" },
  "provenance": {
    "ephemeris_provider": "swiss", "ephemeris_version": "swe-2.10.03",
    "ayanamsa": "lahiri", "zodiac": "sidereal",
    "calc_timestamp": "2026-08-04T09:05:03Z", "confidence": 0.98
  }
}
```

### 7.3 Create invitation → Accept

```http
POST /v1/couples/invitations
Idempotency-Key: 01J9ZD0inv

{ "channel": "link", "invitee_hint": "Rohan", "role": "seeker" }
```
```http
201 Created
{
  "id": "inv_01J9ZD1", "status": "pending", "code": "DIL-7K2Q-9XA4",
  "accept_url": "https://dilchat.com/join/DIL-7K2Q-9XA4",
  "inviter_user_id": "usr_01J9ZA1", "expires_at": "2026-08-11T09:10:00Z", "created_at": "2026-08-04T09:10:00Z"
}
```
Rohan (a different authenticated account) accepts:
```http
POST /v1/couples/invitations/inv_01J9ZD1:accept
Idempotency-Key: 01J9ZD2acc

{ "code": "DIL-7K2Q-9XA4" }
```
```http
201 Created
Location: /v1/couples/cpl_01J9ZD3

{
  "couple": {
    "id": "cpl_01J9ZD3", "status": "active",
    "members": [
      { "user_id": "usr_01J9ZA1", "role": "seeker", "private_scope": "PRIVATE_A" },
      { "user_id": "usr_01J9ZR9", "role": "partner", "private_scope": "PRIVATE_B" }
    ],
    "created_at": "2026-08-04T09:12:00Z"
  }
}
```
Replaying the `:accept` (or a second accepter) → `409 INVITATION_USED`; after expiry →
`410 INVITATION_EXPIRED`.

### 7.4 Shared Guna Milan scorecard

```http
GET /v1/couples/cpl_01J9ZD3/guna-milan
```
```http
200 OK
{
  "couple_id": "cpl_01J9ZD3",
  "total": { "score": 28.5, "max": 36 },
  "components": [
    { "koota": "varna",    "score": 1, "max": 1, "note": "work/temperament ordering satisfied" },
    { "koota": "vashya",   "score": 2, "max": 2, "note": "mutual control balance" },
    { "koota": "tara",     "score": 1.5, "max": 3, "note": "birth-star compatibility, directional" },
    { "koota": "yoni",     "score": 3, "max": 4, "note": "traditional constitutional compatibility (non-sexualized, DEC-021)" },
    { "koota": "graha_maitri", "score": 4, "max": 5, "note": "planetary friendship of Moon lords" },
    { "koota": "gana",     "score": 5, "max": 6, "note": "temperament class harmony" },
    { "koota": "bhakoot",  "score": 7, "max": 7, "note": "no bhakoot dosha" },
    { "koota": "nadi",     "score": 5, "max": 8, "note": "constitutional compatibility only — never medical/genetic (DEC-021)" }
  ],
  "doshas": { "bhakoot_dosha": false, "nadi_dosha": false, "cancellations_applied": [] },
  "trace": {
    "seeker": { "moon_rashi": "vrishabha", "moon_nakshatra": "rohini", "nadi": "antya", "gana": "manushya" },
    "partner": { "moon_rashi": "tula", "moon_nakshatra": "swati", "nadi": "aadi", "gana": "deva" }
  },
  "provenance": {
    "ephemeris_provider": "swiss", "ephemeris_version": "swe-2.10.03",
    "ayanamsa": "lahiri", "zodiac": "sidereal",
    "rule_pack_id": "ashtakoota_lahiri_classical_v1",
    "interpretation_pack_version": "dilchat_interp_v1",
    "calc_timestamp": "2026-08-04T09:13:00Z", "confidence": 0.97
  }
}
```
The eight components always sum-cap at 36; `total.score` is the classical Ashtakoota total
(DEC-019 family 1) — immutable for this version tuple, and AI may explain but never alter it.

### 7.5 Daily interest profile (12 interest scores)

```http
GET /v1/me/daily?date=2026-08-04
```
```http
200 OK
{
  "date": "2026-08-04", "local_timezone": "Asia/Kolkata",
  "transit_moon": { "rashi": "mithuna", "nakshatra": "ardra", "pada": 2 },
  "natal_moon_house": 2,
  "emotional_climate": { "label": "reflective", "valence": 0.35, "energy": 0.5 },
  "interest_scores": [
    { "theme": "communication",   "score": 0.82 },
    { "theme": "intimacy",        "score": 0.44 },
    { "theme": "adventure",       "score": 0.61 },
    { "theme": "stability",       "score": 0.73 },
    { "theme": "finances",        "score": 0.38 },
    { "theme": "family",          "score": 0.55 },
    { "theme": "career",          "score": 0.66 },
    { "theme": "health",          "score": 0.49 },
    { "theme": "spirituality",    "score": 0.70 },
    { "theme": "creativity",      "score": 0.58 },
    { "theme": "social",          "score": 0.47 },
    { "theme": "rest",            "score": 0.63 }
  ],
  "transitions": [
    { "event": "nakshatra_change", "to": "punarvasu", "at": "2026-08-04T18:42:00Z" }
  ],
  "disclaimer": "Reflective guidance only — not medical, psychiatric, legal, financial, or predictive advice (DEC-021).",
  "provenance": {
    "ephemeris_provider": "swiss", "ephemeris_version": "swe-2.10.03",
    "ayanamsa": "lahiri", "zodiac": "sidereal",
    "transit_model_version": "dilchat_transit_v1",
    "interest_model_version": "dilchat_interest_v1",
    "interpretation_pack_version": "dilchat_interp_v1",
    "calc_timestamp": "2026-08-04T00:00:05Z", "confidence": 0.95
  }
}
```

### 7.6 Consent grant → grant → revoke

Propose a bounded projection of a private reflection into the shared space:
```http
POST /v1/consent/grants
Idempotency-Key: 01J9ZE0cg

{
  "couple_id": "cpl_01J9ZD3",
  "artifact_kind": "reflection_summary",
  "source_scope": "PRIVATE_A",
  "projection": { "title": "What I need this week", "summary": "I'd value one unhurried evening together." },
  "revocation_policy": "revocable"
}
```
```http
201 Created
{ "id": "cg_01J9ZE1", "status": "proposed", "couple_id": "cpl_01J9ZD3", "owner_user_id": "usr_01J9ZA1",
  "artifact_kind": "reflection_summary", "source_scope": "PRIVATE_A", "created_at": "2026-08-04T09:20:00Z" }
```
The **owner** authorizes it (only the data owner may `:grant`):
```http
POST /v1/consent/grants/cg_01J9ZE1:grant
Idempotency-Key: 01J9ZE2grant

200 OK
{ "id": "cg_01J9ZE1", "status": "granted", "shared_artifact_id": "sha_01J9ZE3",
  "granted_at": "2026-08-04T09:21:00Z", "revocation_policy": "revocable" }
```
Later, revoke:
```http
POST /v1/consent/grants/cg_01J9ZE1:revoke
Idempotency-Key: 01J9ZE4revoke

200 OK
{ "id": "cg_01J9ZE1", "status": "revoked", "revoked_at": "2026-08-05T07:00:00Z",
  "shared_artifact_id": "sha_01J9ZE3", "shared_artifact_state": "withdrawn" }
```
At no point is the partner told a private conversation exists — only the explicitly granted
`SharedArtifact` ever surfaces to them (DEC-013).

### 7.7 Dual-approval agreement

```http
POST /v1/couples/cpl_01J9ZD3/agreements
Idempotency-Key: 01J9ZF0agr

{ "title": "Weeknight phones-down hour", "body": "20:00–21:00 no phones, three nights a week.",
  "compromise_session_id": "cs_01J9ZF9" }

201 Created
{ "id": "agr_01J9ZF1", "status": "draft", "author_user_id": "usr_01J9ZA1", "created_at": "2026-08-04T09:30:00Z" }
```
```http
POST /v1/agreements/agr_01J9ZF1:submit
200 OK
{ "id": "agr_01J9ZF1", "status": "pending_approval", "approvals": [] }
```
Member A approves:
```http
POST /v1/agreements/agr_01J9ZF1:approve
Idempotency-Key: 01J9ZF2apprA

200 OK
{ "id": "agr_01J9ZF1", "status": "pending_approval",
  "approvals": [ { "user_id": "usr_01J9ZA1", "approved_at": "2026-08-04T09:31:00Z" } ],
  "required": 2, "received": 1 }
```
A second `:approve` from the **same** member is rejected:
```http
409 CONFLICT { "code": "CONFLICT", "detail": "You have already approved this agreement." }
```
Member B approves — the commit point:
```http
POST /v1/agreements/agr_01J9ZF1:approve
Idempotency-Key: 01J9ZF3apprB

200 OK
{ "id": "agr_01J9ZF1", "status": "active",
  "approvals": [
    { "user_id": "usr_01J9ZA1", "approved_at": "2026-08-04T09:31:00Z" },
    { "user_id": "usr_01J9ZR9", "approved_at": "2026-08-04T09:33:00Z" }
  ],
  "required": 2, "received": 2, "activated_at": "2026-08-04T09:33:00Z" }
```
An agreement in `pending_approval` with only one approval returns
`403 DUAL_APPROVAL_REQUIRED` if any member tries to attach commitments before activation.

### 7.8 Error examples

**SHARED without active membership** (unpaired, or never a member):
```http
GET /v1/couples/cpl_01J9ZD3/climate?date=2026-08-04

403 Forbidden
Content-Type: application/problem+json
{
  "type": "https://errors.dilchat.com/couple-not-active",
  "title": "Couple not active", "status": 403, "code": "COUPLE_NOT_ACTIVE",
  "detail": "Your membership in this couple is not active.",
  "trace_id": "trc_01J9ZG0"
}
```
**Cross-private read → 404, never 403** (§4.3):
```http
GET /v1/birth-profiles/bp_someone_elses

404 Not Found
Content-Type: application/problem+json
{
  "type": "https://errors.dilchat.com/not-found",
  "title": "Not found", "status": 404, "code": "NOT_FOUND",
  "detail": "No such resource.",
  "trace_id": "trc_01J9ZG1"
}
```
The `404` is deliberately indistinguishable from a nonexistent id — the response never
confirms that the partner's birth profile exists.

**AI schema validation failure:**
```http
POST /v1/ai/draft-agreement
422 Unprocessable Entity
{
  "type": "https://errors.dilchat.com/ai-validation-failed",
  "title": "AI output invalid", "status": 422, "code": "AI_VALIDATION_FAILED",
  "detail": "The generated draft did not conform to the DraftAgreement schema; no unstructured output is ever returned.",
  "trace_id": "trc_01J9ZG2"
}
```

---

## 8. Idempotency, retry, and async-job patterns

### 8.1 Transparent retry with `Idempotency-Key`

```
Client                                   Server
  │  POST /v1/couples/invitations         │
  │  Idempotency-Key: K1  ───────────────▶│  store K1→in_flight, create inv_…, K1→snapshot(201)
  │  ◀───────────────── 201 {inv_…}       │
  │  (network drops the response)         │
  │  POST … Idempotency-Key: K1  ────────▶│  same fingerprint → replay snapshot
  │  ◀── 201 {inv_…}  Idempotency-Replayed: true
```
- Same key + same body → **exactly one** invitation, replayed response.
- Same key + different body → `422 IDEMPOTENCY_KEY_REUSED`.
- Same key while first still running → `409 CONFLICT` + `Retry-After`.

### 8.2 Async job: `202 Accepted` + `Location` + poll

```http
POST /v1/me/export
Idempotency-Key: 01J9ZH0exp
{ "format": "zip", "include": ["birth_profiles","charts","agreements","audit"] }
```
```http
202 Accepted
Location: /v1/me/export/job_01J9ZH1
Retry-After: 5
{ "job_id": "job_01J9ZH1", "status": "queued", "kind": "data_export", "created_at": "2026-08-04T10:00:00Z" }
```
Poll:
```http
GET /v1/me/export/job_01J9ZH1

200 OK   { "job_id": "job_01J9ZH1", "status": "running", "progress": 0.4 }
```
```http
200 OK
{
  "job_id": "job_01J9ZH1", "status": "succeeded",
  "result": { "download_url": "https://exports.dilchat.com/…signed…", "expires_at": "2026-08-04T22:00:00Z", "size_bytes": 84213 },
  "completed_at": "2026-08-04T10:02:11Z"
}
```
A failed job → `{ "status": "failed", "error": { "code": "INTERNAL", "trace_id": "…" } }`
(the poll endpoint itself still returns HTTP `200`; the failure is in the job body).

### 8.3 Account deletion (async, `deletion_pending`)

```http
DELETE /v1/me
Idempotency-Key: 01J9ZH2del
{ "confirm": "asha@example.com" }

202 Accepted
Location: /v1/me/export/job_01J9ZH3   // deletion job resource
{ "job_id": "job_01J9ZH3", "status": "deletion_pending", "grace_until": "2026-08-11T10:05:00Z" }
```
Within the grace window the account is recoverable by logging in; after it, an `arq` sweep
(DEC-006) finalizes hard deletion, unpairs any couple, and revokes all sessions.

### 8.4 Chart calculation fast-path vs saturation fallback

`POST /v1/charts:calculate` normally returns `200` inline (§7.2). Under worker-pool
saturation it may instead return the async shape:
```http
202 Accepted
Location: /v1/charts/chart_01J9ZC3
Retry-After: 2
{ "job_id": "job_01J9ZC9", "status": "queued", "kind": "chart_calculation" }
```
If the ephemeris data/worker pool is unavailable (DEC-007), calculation endpoints return
`503 EPHEMERIS_UNAVAILABLE` (the Moshier fallback lowers `confidence` rather than failing,
so a `503` means even the fallback is down).

---

## 9. Cross-references

| Concern | Authority |
|---|---|
| Canonical versions, module names, scopes | `DILCHAT_DECISION_LOG.md` §0 |
| Consent state machine & `SharedArtifact` | `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md` (DEC-013) |
| Scope guard + PostgreSQL RLS | `DILCHAT_BACKEND_ARCHITECTURE.md` (DEC-012) |
| Astrology math, ambiguous-time handling | `DILCHAT_ASTROLOGY_ENGINE_SPEC.md` (DEC-007/008/017) |
| Guna Milan rule-pack source | `rules/ashtakoota_lahiri_classical_v1/sources.json` (DEC-009) |
| Machine contract | `openapi/dilchat.openapi.yaml` |
```
