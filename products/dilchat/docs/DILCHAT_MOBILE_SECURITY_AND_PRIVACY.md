# DilChat Mobile — Security & Privacy (Phase 1)

> **Phase 1 provides account, profile, invitation, pairing, and consent only.
> Guna Milan and compatibility analysis remain blocked and unavailable.**

## Session & credential security

- **Tokens live only in the platform secure store** (`expo-secure-store` →
  Keychain / Keystore), via `src/auth/storage.ts`. Tokens are **never** placed in
  AsyncStorage, logs, crash messages, analytics, or React state that could serialize.
- **Bearer auth**: the client attaches `Authorization: Bearer <access>` to
  authenticated calls. The backend also verifies the server-side session on every
  request, so a revoked/rotated/logged-out session is rejected even if the access
  token has not expired.
- **Session restoration**: on launch the app checks the secure store for a refresh
  token and restores the signed-in state; the first authenticated call refreshes
  the access token if needed.
- **One controlled refresh**: `HttpClient` performs **exactly one** refresh+retry on
  a 401. If refresh fails it clears all credentials and returns the user to sign-in.
  There is no infinite retry loop.
- **Sign-out** (`AuthContext.signOut`) calls the backend logout (device or all
  devices) and then **always** clears local credentials and the React Query cache —
  even if the network logout fails.
- **Account switching** clears the prior user's cached server state
  (`queryClient.clear()`), so no data leaks across accounts.
- **No fake production auth**: authentication uses the real backend contract. A
  local dev backend is used only in development; no credentials are bundled.

## Privacy model

- **Private ownership**: each person owns their own account and birth profile. The
  backend enforces this with row-level security; the client never reads another
  user's private birth-profile fields (and the paired-status response exposes none —
  only `couple_id`, `status`, and member `scope_slot`s).
- **Pairing ≠ disclosure**: accepting an invitation pairs two accounts but does not
  copy or expose private profile fields into a shared context. Phase 1 shares **no**
  compatibility artifact and calls **no** artifact-sharing consent endpoint.
- **Explicit consent**: the consent screen requires an explicit, unchecked-by-default
  affirmation before the accept/pair call. No preselected consent, no passive
  consent through continued use, no guilt language, no irreversible consent.
- **Revocation**: either paired party can unpair; the backend revokes shared access
  immediately, and the client drops the couple from cache.
- **Existence non-disclosure**: the client relies on the backend's neutral errors
  (no "account exists" disclosure on register; 404-style not-found on unauthorized
  couple/invitation access).

## Data handling in the client

- No natal Moon / Nakshatra / Guna / compatibility value is ever computed or shown
  in the mobile client. The "compatibility" screen states only that analysis is not
  yet available and shows no number or placeholder.
- Request bodies containing credentials are never logged; the error normalizer emits
  user-facing messages that never include tokens or raw server internals.
- The API base URL comes from configuration (`DILCHAT_API_BASE_URL` →
  `app.config.js` → `extra.apiBaseUrl`); no production endpoint is hardcoded. A CI
  guard (`scripts/check-no-prod-endpoint.js`) enforces this.

## CI guards

`dilchat-mobile-ci.yml` runs: lint, strict type-check, unit/component + contract
tests, Expo config validation, the no-hardcoded-endpoint guard, an API
contract-drift check (required routes present; **no** Guna/compatibility route),
and a secret scan. `contents: read` only; no production credentials; no deployment.

## Out of scope (Phase 1)

Push notifications, background biometric lock, certificate pinning, and app-preview
redaction are noted as future hardening. Backgrounding preview redaction is a small
follow-up (the OS snapshot may show the last screen); no sensitive scores exist to
leak in Phase 1.
