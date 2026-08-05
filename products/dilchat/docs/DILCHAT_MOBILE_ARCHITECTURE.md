# DilChat Mobile — Architecture (Phase 1)

> **DilChat mobile Phase 1 provides account, profile, invitation, pairing, and
> consent functionality only. Guna Milan and compatibility analysis remain blocked
> and unavailable.**

## Stack decision & rationale

The monorepo has **web** React frontends (`apps/ugence-governance-studio/frontend`,
`apps/console`) but **no** existing mobile/React-Native convention. Per the phase
brief, when no mobile convention exists we adopt:

| Concern | Choice | Rationale |
|---|---|---|
| Framework | **React Native 0.74 + Expo SDK 51** | fastest path to iOS+Android from one TS codebase; managed workflow, no native build needed for CI |
| Language | **TypeScript (strict)** | matches the repo's typed web frontends; `strict` + `noUncheckedIndexedAccess` |
| Navigation | **Expo Router 3** (file-based) | first-class Expo navigation; typed routes |
| Server state | **@tanstack/react-query 5** | same library the governance-studio frontend uses |
| Secure storage | **expo-secure-store** | Keychain/Keystore-backed; never AsyncStorage for tokens |
| Tests | **jest-expo + @testing-library/react-native** | standard Expo unit/component testing; runs in CI without a simulator |
| API contract | hand-written typed models in `src/api/types.ts`, checked against the live backend OpenAPI by a **contract-drift** CI step | avoids a heavyweight codegen toolchain while still failing on drift |

The app lives under the bounded path **`products/dilchat/mobile/`** and is **not**
wired into any unrelated monorepo build system. It has its own `package.json`,
`app.config.js`, and CI workflow (`.github/workflows/dilchat-mobile-ci.yml`).

## Module layout

```
products/dilchat/mobile/
  app/                     # expo-router routes (screens)
    _layout.tsx            # providers (QueryClient + Auth) + Stack
    index.tsx              # launch / session-loading → redirect
    (auth)/                # sign-in, register (redirects away if signed-in)
    (app)/                 # authenticated area (redirects to sign-in if not)
        home, profile, invite, accept, consent, paired, privacy, settings, compatibility
  src/
    config/env.ts          # API base URL from config (no hardcoded prod endpoint)
    api/types.ts           # typed request/response models (mirror OpenAPI)
    api/errors.ts          # ApiError + normalization
    api/client.ts          # HttpClient: timeout, bearer, ONE refresh+retry, no token logs
    api/endpoints.ts       # one typed function per contract operation
    auth/storage.ts        # SecureStore token storage (+ clearAll)
    auth/AuthContext.tsx   # session state, sign-in/out, refresh, cache clearing
    query/queryClient.ts   # React Query config (no retry on auth/validation)
    query/hooks.ts         # useMe / useBirthProfile / useCurrentCouple / mutations
    validation/birthProfile.ts  # client-side (non-authoritative) form validation
    ui/components.tsx      # accessible primitives (Screen/Button/TextField/…)
  scripts/                 # check-no-prod-endpoint.js, check-contract-drift.js
  __tests__/               # unit / component / contract tests
```

## State separation

- **Server state** — React Query (`src/query/hooks.ts`), keyed and cache-cleared on
  sign-out / account switch.
- **Local UI state** — component `useState` (form drafts, toggles).
- **Secure auth state** — `expo-secure-store` only, mediated by `AuthContext`; the
  client never duplicates backend authorization as a security boundary.

## API client behaviour

`HttpClient` (`src/api/client.ts`): configurable base URL, 15 s timeout via
`AbortController` (cancellation-capable), problem+json error normalization to
`ApiError` (network vs timeout vs http), and **exactly one** refresh+retry on a
401 — on refresh failure it clears credentials and signs out. It never logs
tokens, credentials, or request bodies.

## Backend contract

Every screen action maps to an existing backend OpenAPI operation — see
`DILCHAT_MOBILE_API_CONTRACT_MAP.md`. **No backend route, model, or migration was
added or changed** for this phase.

## Mobile phase sequence (post–Phase 1)

Phase 1 (this doc) is **merged**. The approved forward sequence — documentation
only; nothing below is implemented — is:

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 2** | Device & native hardening: native builds, physical-device validation, deep-link foundation, privacy hardening, network resilience, accessibility review | **Not started** (next engineering phase) |
| **Phase 3** | Secure shared partner chat: persistence, sync, delivery states, relationship-scoped authorization, unpair revocation, retention/deletion, abuse/blocking/reporting | Blocked on Phase 2 |
| **Phase 4A–4D** | AI Assist: conversation evidence → hidden Guna structural prior → Moon receptivity → AI Assist overlay | Blocked on Phase 3 + privacy boundaries |

The AI Assist direction (hidden Guna prior at 60 %→30 %, separate temporary Moon
receptivity, progressively dominant conversation evidence, no user-visible Guna
score) is specified in
[`DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md`](DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md),
[`DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md`](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md),
and the [chat-overlay spec](DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md), under founder
decision **DEC-048**. **AI Assist must not be implemented before secure shared
chat (Phase 3) and privacy boundaries exist.**

## Known limitations

- CI runs lint/type-check/tests/config-validation only — it does **not** build
  device binaries or run a simulator (no emulator in CI); on-device verification is
  a manual step documented in the mobile README.
- API models are hand-written and guarded by a contract-drift check rather than
  generated; a future phase may adopt OpenAPI type generation.
- Geocoding of the birthplace is manual (label + lat/long + IANA zone) in Phase 1;
  a place-search integration is out of scope.
