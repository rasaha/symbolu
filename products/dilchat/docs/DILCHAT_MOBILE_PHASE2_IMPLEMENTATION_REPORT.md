# DilChat Mobile — Phase 2 Implementation Report

**Branch:** `claude/dilchat-mobile-phase-2-qllgp7` (logical workstream
`dilchat-mobile-device-pilot`).
**Started from default:** `c89d699c0b7b2a135b0aed14509a3bb373798413`
(`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`).
**Verdict:** `MOBILE_PHASE2_IMPLEMENTED_VALIDATION_PENDING` — implementation and
all automated/toolchain/emulator-independent gates pass; native **compiled builds**
(Android gradle / iOS Xcode), emulator/simulator runs, and **physical-device**
execution are unavailable in this Linux environment and are deferred with evidence.

## 1. Live-state verification (Section 1)

| Item | Verified value |
|------|----------------|
| Repository | `rasaha/symbolu` |
| Authoritative default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default tip SHA | `c89d699c0b7b2a135b0aed14509a3bb373798413` |
| PR #1341 (Mobile Phase 1) | merged 2026-08-05T00:17:05Z |
| PR #1342 (AI Assist req docs) | merged 2026-08-05T02:13:11Z; merge SHA = default tip ✓ |
| Phase 2 branch vs default | 0 ahead / 0 behind (started exactly at default) |
| `dilchat-mobile-device-pilot` | at `dda36011…` = 0 unique commits (stale ancestor; no work to preserve) |
| Open DilChat mobile PRs | none |
| Forbidden impls (chat/AI Assist/Moon/Guna exec) in mobile | none found |

No STOP condition triggered.

## 2. Baseline reproduction (Section 4)

- Mobile: `npm ci` (1394 pkgs) · `eslint --max-warnings=0` → 0 · `tsc --noEmit` → 0
  · `jest` → **53/53** (pre-change baseline) · config/endpoint guards OK ·
  contract-drift skips gracefully when OpenAPI unset (CI supplies it).
- **Live integration**: `npm run test:integration` against a real FastAPI +
  **PostgreSQL 16.13** (fresh alembic-migrated DB, production HttpClient) → **9/9**.
- Backend: **not modified**; not re-run here (Phase 1 report records ruff/mypy clean,
  pytest 201/0-skipped, one Alembic head `b2c3d4e5f6a7`). No backend file changed by
  Phase 2 (see §7).

Baseline green → Phase 2 work proceeded.

## 3. What was implemented

### A. Toolchain (see Build & Toolchain Report)
Fixed the `ajv-keywords`/`ajv` hoist crash; `expo config`, Metro export, and
`expo prebuild` now run. Added `ajv@^8` devDep + `expo-linking@6.3.1`.

### B. Native config hardening
`app.config.js`: `android.blockedPermissions` (removes 4 unused perms → only
`INTERNET`), `android.allowBackup:false`, `ios.infoPlist.ITSAppUsesNonExemptEncryption:false`,
`extra.invitationLinkHosts:[]` (deep-link host allowlist). Verified in the generated
AndroidManifest.

### C. Deep-link invitation flow
- `src/deeplink/parse.ts` — **versioned, allowlisted** parser. Only the
  `invitation` intent is recognized; any other path/scheme/host is **ignored, never
  routed** (no open redirect, no arbitrary internal route). `http` and untrusted
  HTTPS hosts rejected; version required; token validated & URL-decoded; fragments
  never read. `buildInvitationLink()` emits the canonical `dilchat://invitation?v=1&token=…`.
- `src/invitation/token.ts` — token normalization (strip whitespace/wrapping;
  reject prose, short/garbage input; charset `[A-Za-z0-9_-]{16,512}` matching the
  backend's `token_urlsafe(48)`).
- `src/invitation/pendingInvitation.ts` — **in-memory-only** pending store (token
  minimization: never persisted to SecureStore/AsyncStorage/logs/analytics/crash;
  cleared on accept/reject/invalidate/sign-out/account-switch).
- `src/invitation/router.ts` — pure policy: signed-out → sign-in (context
  preserved & resumed after auth); signed-in → **consent** (never a direct accept);
  loading → wait (no premature sign-in flash).
- `src/invitation/useInvitationDeepLinks.ts` — interceptor mounted at root; owns
  initial + subsequent URLs via `expo-linking`; parses, stores, navigates.
- `app/(app)/consent.tsx` — accept runs **at most once** (in-flight guard + phase
  state); **terminal** rejections (400/404/409/410/422 → invalid/expired/consumed/
  self/already-paired) clear the token and show a way out; **ambiguous** transport
  failures keep a neutral, user-retryable recovery state (**no blind retry**).
- `app/(app)/accept.tsx` — accepts a pasted **code or full link** (extracts the
  token via the parser; rejects prose/other-route links).
- `app/(app)/invite.tsx` — shares a versioned deep link via the OS share sheet
  (user-initiated; never logged).

### D. Lifecycle & session resilience
- `src/auth/storage.ts` — reads **never throw**: a locked/corrupt/unavailable
  keychain or a malformed (empty/whitespace) stored token degrades to "no session"
  (prevents crash / infinite-loading). `clearAll` best-effort.
- `src/auth/AuthContext.tsx` — session restore can't hang in `loading`; sign-out /
  account-switch clears the query cache **and** the pending invitation. Existing
  single-flight refresh (`HttpClient.dedupedRefresh`) preserved — no refresh storm,
  no client-caused reuse revocation.

### E. Offline & interruption
Accept and unpair never blind-retry an ambiguous response; `paired.tsx` treats an
already-unpaired 404/409 as done and offers a "Check current status" refresh of
authoritative server state. React Query mutations `retry:false`.

### F. Privacy
- `src/privacy/AppSwitcherShield.tsx` — opaque, content-free, accessibility-hidden
  cover whenever the app is not `active`, so app-switcher/Recents snapshots reveal
  no birth data, token, email, or pairing state; removed on resume (no permanent
  blank).
- Device-only secure storage (`WHEN_UNLOCKED_THIS_DEVICE_ONLY`) + Android backup off.
- Cross-account isolation: query cache + pending invitation cleared on sign-out.

### G. Accessibility
`ErrorText` now announces assertively with `role="alert"` (color is never the only
error signal); `Loading` exposes a labeled `progressbar`; consent checkbox carries
state+hint. Existing roles/labels/touch-targets retained.

## 4. Test results

| Suite | Count |
|-------|-------|
| Unit/component (`jest`) | **127 tests / 19 suites** (was 53/10; **+74**) |
| Live integration (real FastAPI + PostgreSQL 16.13) | **9/9** |

> Merge-audit update: the count rose from 122 → **127** when the independent
> merge audit added 5 deep-link canonicalization regression tests (mixed-case
> host, port stripping, duplicate-token first-wins, trailing-segment / backslash
> route-escape). See `DILCHAT_MOBILE_PHASE2_MERGE_AUDIT.md`.
| Backend regression | unchanged (no backend files touched) |

New/expanded test files: `deeplink.parse` (route allowlist, versioning, host
allowlist, token/fragment handling), `invitation.token`, `invitation.pending`,
`invitation.router`, `accept.screen`, `consent.screen` (single-accept, terminal vs
recoverable), `paired.screen` (ambiguous-unpair no-retry, 404-as-done),
`authContext.isolation` (cross-account cache + pending clear), `storage.resilience`
(keychain failure / malformed token), `appSwitcherShield`, `components.a11y`.

Tests assert behavior (navigation, single-invocation, state transitions,
announcements), not component snapshots.

## 5. Toolchain / build results

`expo config` exit 0 · Metro export exit 0 (2.28 MB Hermes bundle) · `expo-doctor`
16/17 in CI (the one failing check is a non-blocking SDK-version *suggestion* —
`expo@51.0.28` vs `~51.0.39`, `expo-router@3.5.23` vs `~3.5.24`; locally 14/17
because 3 checks additionally need `api.expo.dev`, which egress blocks) ·
`expo prebuild --platform android` exit 0 (manifest validated & hardened).
**Android Gradle debug build** now runs in CI (Track A `android-build` job, official
Google SDK on a GitHub runner). Android emulator + installed-app launch (no
`/dev/kvm` here), all iOS (no macOS/Xcode), and physical devices remain
**deferred** — see `DILCHAT_MOBILE_PHASE2_NATIVE_VALIDATION_REPORT.md`.

## 6. Verdict rationale

Not `BLOCKED` (no security/privacy/contract/lifecycle/isolation defect). Not
`DEVICE_PILOT_READY` (no emulator/simulator or compiled build ran here). Not
`MERGE_READY` (native compiled-build + device evidence are merge-relevant and
unavailable). **`MOBILE_PHASE2_IMPLEMENTED_VALIDATION_PENDING`** is the accurate
verdict: implementation complete, all runnable gates green **as of the
merge-audit head** (see below), native-platform and physical-device evidence
pending on capable hardware.

> Merge-audit correction: at the originally reported head the mandatory
> `Mobile lint / typecheck / test / guards` CI job was **red** — a single
> cold-cache test (`authContext.isolation` sign-out) exceeded Jest's 5 s default
> on the first, transform-heavy suite render (~8–10 s cold, <0.5 s warm). The
> audit raised the default Jest timeout to 20 s (`jest.setup.ts`); the suite now
> passes 127/127 across repeated cold runs. No behavior assertion changed. Full
> record in `DILCHAT_MOBILE_PHASE2_MERGE_AUDIT.md`.

## 7. Confirmations

- **No** secure chat, messaging, AI Assist, conversation preference learning, Moon
  receptivity, Guna/Koota/Dosha/Parihara execution, compatibility scoring, or any
  such route/value was implemented. Guna rule pack remains non-executable.
- **No** backend model, migration, API, or source module changed (changes are
  confined to `products/dilchat/mobile/**` and `products/dilchat/docs/**` plus the
  mobile CI workflow).
- **No** production credentials, deployment, or app-store release.
- Only synthetic accounts and synthetic birth data were used.
