# DilChat Mobile Phase 1 — Implementation Report

> **DilChat mobile Phase 1 provides account, profile, invitation, pairing, and
> consent functionality only. Guna Milan and compatibility analysis remain blocked
> and unavailable.**

## Scope delivered

The first mobile vertical slice: launch/session-restore, register + sign-in,
user-owned birth-profile create/edit, partner invitation, invitation acceptance,
explicit pairing consent, paired status, unpairing, and sign-out — plus a
"compatibility unavailable" screen. No Guna/compatibility/astrology/chat/AI.

## Stack

Expo SDK 51 · React Native 0.74 · TypeScript strict · Expo Router 3 ·
@tanstack/react-query 5 · expo-secure-store. Node 22 / npm 10. App path:
`products/dilchat/mobile/`. See `DILCHAT_MOBILE_ARCHITECTURE.md`.

## Backend routes used (all pre-existing; no backend change)

`POST /v1/auth/register|login|refresh|logout|logout-all`, `GET /v1/users/me`,
`POST /v1/birth-profiles`, `GET|PATCH /v1/birth-profiles/me`,
`POST /v1/couples/invitations`, `POST /v1/couples/invitations/{token}/accept`,
`GET /v1/couples/current`, `POST /v1/couples/{couple_id}/unpair`. Full mapping in
`DILCHAT_MOBILE_API_CONTRACT_MAP.md`.

- **Backend additions:** none.
- **Migrations added:** none.
- **Database/model changes:** none.

## Screens implemented (12)

launch/session-loading (`app/index.tsx`), sign-in, register, home/status, birth
profile create/edit, invite, accept, pairing-consent, paired status, privacy,
settings/sign-out, compatibility-unavailable.

## Session security

- Tokens only in `expo-secure-store`, pinned `WHEN_UNLOCKED_THIS_DEVICE_ONLY`
  (excluded from device backups / Keychain sync); never AsyncStorage/logs/analytics.
- Bearer auth + server-side session revocation honored.
- Session restoration on launch; **one** controlled refresh+retry on 401, then
  sign-out on failure (no infinite retry).
- **Single-flight refresh:** concurrent 401s share ONE backend refresh. The
  backend rotates refresh tokens and revokes the whole session chain on reuse, so
  de-duplicating the refresh prevents a spurious sign-out under parallel requests.
- Sign-out and account-switch clear credentials **and** the React Query cache.
- API base URL configuration-driven; no hardcoded production endpoint (CI-guarded).

## Profile privacy

- Client reads only the caller's own profile; the paired-status payload exposes no
  partner private fields (only `couple_id`, `status`, member `scope_slot`s).
- No natal Moon / Nakshatra / Guna computed or displayed anywhere in the client.
- Client-side validation is a UX aid; the backend remains authoritative. Device
  time zone is not assumed to be the birth zone (IANA zone required).

## Invitation, pairing, consent, unpairing

- Invitation token shown once in a selectable card; never logged.
- Accept flow routes through the consent screen; **explicit, unchecked-by-default**
  consent gates the accept call (connect disabled until consented).
- Paired status shows minimal metadata; unpair requires a confirm step and revokes
  shared access immediately (couple dropped from cache).

## Tests (mobile)

`@testing-library/react-native` + jest-expo. **10 suites, 53 tests, all passing.**
Coverage: birth-profile validation + serialization (midnight, DST-transition,
device-zone independence); API error normalization; secure-storage
save/restore/clear; HttpClient (success, 204, non-ok→ApiError, single refresh+retry,
**concurrent-401 single-flight**, refresh reset, onAuthLost, bearer header, no
token logging); sign-in / profile / consent (gated) / paired (unpair) /
compatibility (no score) screens; and a contract-level test driving the real
client + endpoints against a fetch mock over the full journey.

**Live backend integration (new): 9/9.** `integration/live.backend.test.ts`
drives the PRODUCTION client + endpoints against a real FastAPI + PostgreSQL 16
(fresh migrated DB, started by `scripts/run-integration.sh`; Node's real fetch).
It exercises real JWT, refresh-token rotation + reuse detection, request/response
schemas, problem+json errors, invitation lifecycle, consent-gated pairing, RLS
privacy isolation, and unpairing revocation — and FAILS (never skips) when the
backend is unavailable. Fixtures use only synthetic names/dates/places/codes.

## Verified gates (exact)

**Mobile** (`products/dilchat/mobile`, Node 22.22.2):
- `npx tsc --noEmit` → **exit 0**
- `npx eslint . --ext .ts,.tsx --max-warnings=0` → **exit 0**
- `npx jest --ci` → **10 suites / 53 tests passed**
- `npm run test:integration` → **9/9 vs real FastAPI + PostgreSQL 16**
- `npm run check:config` → OK · `npm run check:endpoint` → OK ·
  `npm run check:contract` (vs live backend OpenAPI) → **13 routes present, no
  Guna/compatibility route**

**Backend** (unchanged; Python 3.12, PostgreSQL 16):
- ruff clean · mypy clean (53 files) · **201 pytest passed / 0 skipped**
- migration up/down/up clean, single Alembic head `b2c3d4e5f6a7`
- OpenAPI 3.1 valid, no Guna/compatibility route · rule-pack validator PASS ·
  `RULE_PACK_BLOCKED` / `executable:false` preserved.

## CI

`.github/workflows/dilchat-mobile-ci.yml` (actionlint-clean): install → lint →
strict type-check → tests → config validation → no-prod-endpoint guard → API
contract-drift (generates the backend OpenAPI and checks required routes + no
Guna/compatibility route) → secret scan. A second **`integration` job** stands up
PostgreSQL 16 + the real FastAPI backend and runs the production client against it
(`npm run test:integration`), failing if the backend is unavailable. `contents:
read` only; no production credentials; no device build; no deployment. The backend
`dilchat-ci` workflow is unchanged.

## Known limitations

- CI does not build device binaries or run a simulator (no emulator available);
  on-device verification is a documented manual step (Phase 2 device pilot).
- `expo-doctor` / `expo config` / `expo export` cannot run in this install: a
  transitive `ajv-keywords` package resolves a `.ts` source file inside
  `@expo/cli` and exits 1. Config validation uses the deterministic
  `check:config`; a true Metro export/bundle is deferred to Phase 2.
- API models are hand-written and guarded by contract-drift rather than generated.
- Birthplace entry is manual (label + lat/long + IANA zone); no place-search yet.
- App-preview redaction on backgrounding is a noted future hardening (no sensitive
  scores exist to leak in Phase 1).
- `expo config` (Expo CLI) has a transitive `ajv-keywords` require bug in this
  install; config validation uses a deterministic Node check (`check:config`) instead.

## Guna fail-closed

No Guna/Koota/compatibility value is computed or exposed. The compatibility screen
states only "Compatibility analysis is not yet available." The rule pack remains
`RULE_PACK_BLOCKED` / `executable:false`; no source frozen; domain review pending.
