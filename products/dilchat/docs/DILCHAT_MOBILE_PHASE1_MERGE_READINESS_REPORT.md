# DilChat Mobile Phase 1 — Merge-Readiness Audit Report

> **Phase 1 provides account, private birth-profile, invitation, explicit
> pairing-consent, paired-status, and unpairing functionality only. Guna Milan
> and compatibility analysis remain blocked and unavailable.**

Independent security, privacy, UX, contract, build-reproducibility, and
merge-readiness audit of PR **#1341** (`dilchat-mobile-onboarding-pairing` →
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`).

## 1. Verified live state

| Item | Value |
| --- | --- |
| Repository | `rasaha/symbolu` |
| Authoritative default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default tip at audit start | `87f4fcf5` |
| PR | #1341 — open, not draft, not merged, `mergeable_state: clean` |
| PR head at audit start | `261527a7` |
| Default advanced after branch cut? | No (branch 0 behind, merge-base = default tip) → no sync needed |
| Reviews / unresolved threads / change-requests | none |
| Files changed (pre-audit) | 57, all under `products/dilchat/mobile/`, `products/dilchat/docs/`, and the mobile CI workflow |
| Backend model/migration/source changed | none |
| Alembic heads | one — `b2c3d4e5f6a7` |
| OpenAPI | 3.1.0, 19 paths; no Guna/Koota/compatibility route |
| Authority state | `GUNA_AUTHORITY_VALIDATION_BLOCKED`, `RULE_PACK_BLOCKED`, rule-pack validator PASS (draft, non-executable) |

No STOP condition was triggered.

## 2. Baseline reproduction (before fixes)

**Backend** (Python 3.12, PostgreSQL 16, local):
- `ruff check src tests scripts` → clean · `mypy src` → clean (53 files)
- `pytest` → **201 passed / 0 skipped** (the 15 PostgreSQL-gated RLS / SECURITY
  DEFINER / migration / integration tests require `DILCHAT_TEST_DATABASE_URL`;
  without it they module-skip and the visible count is 186 + 3 — the CI provides
  the DB and collects all 201)
- migration upgrade → downgrade base → re-upgrade head, clean; one head
- OpenAPI 3.1 generated + validated; no-Guna guard PASS; rule-pack validator PASS

**Mobile** (Node 22.22.2):
- `npm ci` clean (1393 packages) · `eslint --max-warnings=0` → 0 · `tsc --noEmit` → 0
- `jest` → 10 suites / 48 tests · `check:config` / `check:endpoint` /
  `check:contract` (vs live OpenAPI) → OK, 13 routes, no Guna/compatibility route

## 3. Architecture & dependency review

- App is confined to `products/dilchat/mobile/`. Clear separation: server state
  (React Query), local UI state (component), secure auth state (`AuthContext` +
  `expo-secure-store`). API client is centralized (`src/api`).
- The mobile client references **only** the 13 permitted routes
  (`auth/*`, `users/me`, `birth-profiles*`, `couples/*`). It does **not** call
  `/v1/natal/moon*`, `/v1/consents`, or `/v1/shared-artifacts` — the natal-Moon
  and consent/shared-artifact primitives exist server-side for future phases and
  are deliberately unused here. No compatibility surface anywhere.
- No business-critical authorization lives only in the client; the backend is
  authoritative (validated by the live integration test, §6).
- API base URL is configuration-driven; no hardcoded production endpoint
  (CI-guarded). Dedupe: `react@18.2.0`, `react-native@0.74.5` single resolved
  copies; no nested duplicates.
- **Vulnerabilities:** `npm audit` reports 31 advisories (1 critical, 17 high),
  **all in build/CLI/bundler/prebuild tooling** — `tar`, `cacache`, `@expo/cli`,
  `@react-native-community/cli*`, `xcode`, `@expo/plist`, `@xmldom/xmldom`,
  `postcss`, `@remix-run/*`/`turbo-stream` (web export), `metro-config`, `send`,
  `uuid`. None execute in the on-device runtime path (auth, secure storage, HTTP
  client, screens); `expo-secure-store`, `@tanstack/react-query`,
  `react-native-screens`, `react-native-safe-area-context` carry no advisories.
  Remediation requires an Expo SDK bump (Phase 2). `npm audit fix --force` was
  **not** run (forbidden; would break pinned versions).

## 4. Authentication & session findings

**Defect found and fixed — concurrent-refresh session revocation (high).**
The backend issues **rotating** refresh tokens with **reuse detection**:
presenting an already-rotated token revokes the *entire* session chain
(`AUTH_REFRESH_REUSE`, 401). The home screen fires `useMe` + `useBirthProfile` +
`useCurrentCouple` in parallel; when the shared access token is expired all three
401 simultaneously. The original client called `TokenProvider.refresh()` per
request with no de-duplication, so the 2nd/3rd requests presented the rotated
token → the backend revoked the whole chain → **spurious full sign-out**.

- **Fix:** transport-level **single-flight refresh** in `HttpClient`
  (`dedupedRefresh`): concurrent 401s share one refresh; all waiters receive the
  same refreshed session. Still exactly one refresh+retry per request; still
  signs out on genuine refresh failure. New unit tests prove one refresh for
  three concurrent 401s and that a later, non-overlapping 401 refreshes again.
- The backend's real rotation + reuse behavior is asserted directly by the live
  integration test (present a rotated token twice → 401).

**Hardening — device-only secure storage.** Tokens are now written with
`keychainAccessible: WHEN_UNLOCKED_THIS_DEVICE_ONLY`, excluding them from
encrypted device backups and Keychain iCloud sync (they can never be restored
onto another device).

Confirmed correct (unchanged): tokens only in `expo-secure-store` (no
AsyncStorage, no logs — **zero `console.*` in shipped `src`/`app`**); session
restore runs once on launch; refresh failure clears credentials **and** the
React Query cache; sign-out calls the backend and still clears locally when the
network fails; sign-out and account switch call `queryClient.clear()`; the
`(app)` route group redirects to sign-in on `signed-out` (no authenticated route
survives logout); session expiry returns to auth without a loop
(auth-error queries are not retried); the one retry is on 401 only — a
pre-processing rejection — so non-idempotent mutations are never blind-retried
(mutations also use `retry: false`).

## 5. Refresh-concurrency, secure-storage, account-switch results

| Check | Result |
| --- | --- |
| Concurrent 401s → single refresh | **PASS** (new `client.test.ts` single-flight test) |
| Non-overlapping later 401 refreshes again | PASS |
| Refresh failure → clear creds + cache + sign out | PASS |
| Tokens device-only (no backup/sync) | PASS (fix) |
| Account switch cannot expose prior cache | PASS (`queryClient.clear()` on sign-in & sign-out) |
| No token in logs/analytics/snapshots | PASS |

## 6. Real backend integration coverage

New live test: `integration/live.backend.test.ts`, run by
`scripts/run-integration.sh` (fresh migrated PostgreSQL 16 + real `uvicorn`
FastAPI) via `jest.integration.config.js` (Node env, Node's real `fetch`,
**production** `HttpClient` + `endpoints` + `errors`). It **fails loudly** if the
backend is unavailable — an absent server never reads as a pass. Synthetic
identities/birth data only. **9/9 passing.**

Exercised end-to-end with three independent users:
- register A/B/C → login all (real JWT issuance)
- create private birth profiles (A EXACT, B APPROXIMATE)
- each reads only their own profile; a profileless user gets **404**, never
  another's data (there is no `/birth-profiles/{id}` route → structural isolation)
- A creates an invitation; **self-acceptance rejected (422 `VALIDATION_ERROR`)**
- B accepts → couple `ACTIVE`, 2 members; the paired payload carries only
  `user_id`/`scope_slot`/`status` (no private birth fields)
- consumed token reused by C → **409**; invalid token → **404 `INVITATION_INVALID`**
  (cross-private uses NOT_FOUND, never FORBIDDEN → no existence leak)
- both partners observe the couple; unrelated C sees **404**
- already-paired A cannot open a new invitation → **409 `CONFLICT`**
- **unpair → 204; both partners immediately 404**; a stale `couple_id` cannot
  re-unpair (404) → revocation is immediate
- **refresh-token rotation + reuse detection** validated directly (rotated token
  re-presented → 401)

What is **not** exercised here (classified, not hidden): the React Native UI
render tree against the live backend, native modules, and on-device secure store
(these need a device/emulator — see §11).

## 7. Invitation / pairing edge cases

Backend semantics were read from source and confirmed live: self-accept → 422;
already-used → 409 `INVITATION_USED`; expired → 409 `INVITATION_EXPIRED`; invalid
→ 404 `INVITATION_INVALID`; already-paired → 409 `CONFLICT`; unpair revokes both
memberships immediately. Client behavior: backend state is authoritative;
`useCurrentCouple` maps 404 → "no connection"; mutation buttons disable while
pending (no duplicate submit); ambiguous network failures are surfaced, not
blind-retried (`retry: false`); consumed/expired invitations are not presented as
reusable; the invitation token is shown in a selectable card and **never logged**.

## 8. Consent & privacy

- Consent is **unchecked by default**; the connect action is
  `disabled={!agreed || !token}` and runs the accept mutation **only** after the
  explicit toggle. No passive/pre-selected consent, no coercive language, no
  irreversibility claim. Seven neutral privacy points, including "Compatibility
  analysis is not yet available."
- Pairing consent in Phase 1 is the explicit client gate before the
  authenticated `accept` call; the server-side `/v1/consents` primitive is for
  future bounded-artifact sharing and is intentionally unused.
- Privacy: each user owns their private profile; the paired payload exposes no
  raw private fields; no cross-user cache reuse (static keys + `clear()` on
  auth transitions); no background prefetch of a partner's profile; no private
  payload logged; sign-out/unpair drop the couple from cache.
- **App-switcher screenshot redaction is deferred to Phase 2** (documented, not
  claimed). No sensitive scores exist to leak in Phase 1.

## 9. Accessibility & UX

Shared primitives (`ui/components.tsx`): `Button` disables while `loading`
(duplicate-submit guard) with `accessibilityRole="button"` +
`accessibilityState`; `TextField` associates a label (`nativeID` +
`accessibilityLabelledBy`) and announces errors via a polite live region;
`Loading` = `progressbar`; `Heading` = `header`; touch targets ≥ 48–52 px;
keyboard-safe scroll (`keyboardShouldPersistTaps`). Every screen has visible
loading/empty/error states and shows normalized messages (never raw backend
error objects). No deterministic/marital relationship claims. No redesign was
performed.

## 10. Birth-profile serialization

Fields match the backend schema; **no natal Moon/Nakshatra/Guna computed in JS**;
the client sends the literal `birth_date` (`YYYY-MM-DD`) + `birth_time_local`
(`HH:MM`) + IANA zone and never converts by device zone. New tests lock: midnight
preserved (no day shift), a DST-transition local time forwarded verbatim (client
never resolves it), birth zone independent of device zone, plus existing coverage
of missing time (UNKNOWN), approximate time (uncertainty 1–720), and malformed
date/zone. Cancelled edits do not mutate cached server state; profile data is
cleared on account switch/logout.

## 11. Build & configuration reproducibility

- `npm ci` reproducible (1393 packages); `check:config` validates config
  shape/plugins and absence of a baked endpoint deterministically.
- **`expo-doctor`, `expo config`, and `expo export` cannot run in this install:**
  a transitive `ajv-keywords` package resolves a **`.ts` source file**
  (`ajv-keywords/src/definitions/typeof.ts`) inside `@expo/cli`, so all three
  exit 1. This is a node_modules tooling defect, not app code, and does not
  affect CI (which uses `check:config`). A true Metro export/bundle is therefore
  **deferred**; it is not claimed here. Best available bundle-integrity evidence:
  the jest-expo suite compiles and executes the entire app module graph (all 12
  screens render) and strict `tsc` + `eslint` pass.
- **Native Android/iOS builds and physical-device testing are unavailable in
  this environment** and are explicitly **deferred to Phase 2** (device-pilot
  branch) — not claimed. No signing credentials or production secrets were added.

## 12. CI changes

`.github/workflows/dilchat-mobile-ci.yml` (actionlint-clean): unchanged existing
`mobile` job (install → lint → strict typecheck → tests → config validation →
no-prod-endpoint guard → OpenAPI contract-drift → secret scan). **Added a second
`integration` job**: PostgreSQL 16 service + Python 3.12 + `pip install -e .`
(backend) + `npm ci` + `npm run test:integration`, which starts a fresh migrated
DB and real FastAPI and drives the production client. `contents: read` only; no
`pull_request_target`; no secrets; no deployment; concurrency cancellation
retained. `run-integration.sh` uses `set -euo pipefail`, no `tee`, and fails when
the backend never becomes healthy — no silent skips. `expo-doctor`/export are
intentionally **not** added (unstable in this install; would fail — see §11).

## 13. Security & hygiene scans

Clean: no private keys/tokens/passwords in tracked source (test passwords are
synthetic constants); no hardcoded non-local endpoints; no `.env`, database,
keystore, provisioning, or binary/mobile-build artifacts committed; no
real-person data (only `example.com`/`example.test`; the sole third-party email
is a maintainer notice inside `package-lock.json`); no Guna/Koota/compatibility
value; **no `console.*` in shipped `src`/`app`**.

## 14. Files changed by the audit

- `src/api/client.ts` — single-flight refresh (`dedupedRefresh`)
- `src/auth/storage.ts` — `WHEN_UNLOCKED_THIS_DEVICE_ONLY`
- `jest.setup.ts` — mirror the SecureStore constant in the mock
- `__tests__/client.test.ts` — 2 single-flight/refresh-reset tests
- `__tests__/validation.birthProfile.test.ts` — 3 serialization tests
- `integration/` (new) — live test, Node jest config, babel config, expo-constants stub, setup
- `scripts/run-integration.sh` (new) — fresh-DB + FastAPI orchestrator
- `package.json` — `test:integration` script; exclude `integration/` from unit run
- `.github/workflows/dilchat-mobile-ci.yml` — real-backend integration job
- docs — this report; updated implementation report / README facts

## 15. Test totals (post-audit)

- **Mobile unit/component/contract:** 10 suites / **53 tests** (was 48; +2
  refresh single-flight, +3 serialization)
- **Mobile live integration:** **9/9** against real FastAPI + PostgreSQL 16
- **Backend:** **201 passed / 0 skipped**; one Alembic head; OpenAPI 3.1 valid,
  no Guna/compatibility route; rule-pack validator PASS

## 16. Limitations (carried to Phase 2 — `dilchat-mobile-device-pilot`)

- Physical-device testing; native iOS build (macOS/Xcode); native Android build.
- True Metro `expo export`/bundle + `expo-doctor` (blocked by the `ajv-keywords`
  `.ts` require bug in this install).
- App-switcher screenshot redaction for sensitive screens.
- Build-tooling dependency advisories (Expo SDK bump).
- Production identity/provider configuration; app-store signing/release.
- Place-search for birthplace (manual lat/long + IANA zone for now).

## 17. Merge recommendation

All security, privacy, authorization, real-backend integration, contract, and CI
gates pass. The one material defect found (concurrent-refresh session revocation)
is fixed and covered by tests. The only remaining work is device/native-build and
production-configuration items that do not undermine the internal mobile
foundation and are explicitly deferred to Phase 2.

**Verdict: `MOBILE_PAIRING_MERGE_READY_WITH_LIMITATIONS`.**

Guna authority remains blocked and no compatibility scoring is exposed.
