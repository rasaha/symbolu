# DilChat Mobile — Phase 2 Privacy & Lifecycle Test Matrix

Maps each Phase 2 privacy / lifecycle / deep-link / offline requirement to its
automated coverage (A = automated test, file in `products/dilchat/mobile/__tests__/`
or `integration/`) or its deferred manual/device gate (M = manual on device). All
automated tests pass (`npm test` → 122/122; `npm run test:integration` → 9/9).

## Deep-link invitation (Workstream C)

| Requirement | Coverage |
|---|---|
| Versioned link parsed; unsupported version rejected | A `deeplink.parse` |
| Route allowlist — non-invitation paths never routed (no open redirect) | A `deeplink.parse` (`home`,`settings`,`profile`,`invite`,`accept`,… → `not-an-invitation-route`) |
| HTTPS host allowlist; untrusted host & cleartext http rejected | A `deeplink.parse` |
| Token validated / URL-decoded; token never read from fragment | A `deeplink.parse`, `invitation.token` |
| "Token copied with extra text" / whitespace / wrapping handled | A `invitation.token`, `accept.screen` |
| Signed-out link → sign-in, context preserved, resumed after auth | A `invitation.router` |
| Signed-in link → **consent** (consent never bypassed) | A `invitation.router`, `consent.screen` |
| Consent unchecked by default; accept only after explicit consent | A `consent.screen` |
| Acceptance occurs **exactly once** (repeated/concurrent taps) | A `consent.screen` (double/triple tap → 1 call) |
| Invalid/expired/consumed/self/already-paired → invalidated, cleared | A `consent.screen` (409/… terminal), integration (self 422 / consumed 409 / invalid 404) |
| Ambiguous accept failure → recovery, **no blind retry** | A `consent.screen` (network error → retryable, 2 deliberate attempts) |
| Token cleared on accept/reject/invalidate/sign-out/switch | A `invitation.pending`, `authContext.isolation`, `consent.screen` |
| Pending token stored in memory only (minimization) | A `invitation.pending` (only token/version/receivedAt; store never touches SecureStore) |
| Cold start / foreground / background link delivery | M device (harness) — interceptor uses `Linking.getInitialURL` + `url` event |

## App lifecycle & session resilience (Workstream D)

| Requirement | Coverage |
|---|---|
| Single-flight refresh; concurrent 401s → one refresh (no storm, no reuse revocation) | A `client` (existing), integration (refresh rotation + reuse detection) |
| Refresh failure / session revocation → sign-out, no stale screen | A `client` (`onAuthLost`), root layout redirect |
| Secure-storage read failure → no session, no crash | A `storage.resilience` |
| Malformed stored token → treated absent | A `storage.resilience` |
| Session restore never hangs in loading | A `storage.resilience` + `AuthContext` guard |
| Account switch → no previous-account cache/data | A `authContext.isolation` |
| Sign-out clears session + account-scoped state | A `authContext.isolation` |
| Token never in logs/UI/error | A `client` (never-logs-token), source scan (no console token) |
| Background→foreground; terminate→relaunch; clock/timezone change | M device (harness) |

## Offline & interruption (Workstream E)

| Requirement | Coverage |
|---|---|
| Ambiguous unpair → **no blind retry**; neutral recovery | A `paired.screen` (network → refresh offered, 1 attempt) |
| Already-unpaired (404/409) treated as done | A `paired.screen` |
| Refresh authoritative server state affordance | A `paired.screen` (`refresh-status`) |
| Offline messages neutral, never claim unconfirmed success | A `errors` (`userMessageFor`), `consent.screen` |
| Profile save / create-invitation offline surfaces error | A existing `profile.screen`, `invite` error path |
| No general offline-write queue introduced | (by design — none added) |

## Privacy hardening (Workstream F)

| Requirement | Coverage |
|---|---|
| App-switcher cover while backgrounded; no data in snapshot | A `appSwitcherShield` (inactive/background → cover; active → removed) |
| Cover shows only neutral copy; hidden from a11y tree | A `appSwitcherShield` |
| Tokens device-only secure storage, excluded from backup/sync | Code (`WHEN_UNLOCKED_THIS_DEVICE_ONLY`) + `android.allowBackup:false` + manifest verified |
| No sensitive values in AsyncStorage / plain files / breadcrumbs | Design (SecureStore only); source scan clean |
| Cross-account isolation (A signs out, B signs in) | A `authContext.isolation` |
| Stale deep link cannot restore prior couple state | A `invitation.pending` cleared on sign-out; terminal-accept clears token |
| Screen-capture policy | Documented (see §Screen capture below); app-switcher shield in place |
| Notification safety | N/A — Phase 2 adds **no** notifications |

### Screen-capture policy (decision)
Phase 2 does **not** globally disable screenshots (usability + product decision).
The **app-switcher shield** protects the highest-risk surface (OS snapshots on
background), covering birth-profile, invitation-token, consent, privacy, and paired
screens uniformly. A per-screen `FLAG_SECURE` (Android) / capture-block (iOS) for
the invitation-token and birth-profile screens is a **candidate hardening for the
device pilot**, evaluated against product usability before adoption.

## Accessibility (Workstream G)

| Requirement | Coverage |
|---|---|
| Header/button/checkbox/progressbar roles; labels; busy/disabled state | A `components.a11y`, `consent.screen` |
| Error announced assertively; color not the only signal | A `components.a11y` (`role=alert`, text message) |
| Loading announced with label | A `components.a11y` |
| Touch targets ≥ 44–48 px | Code (`minHeight` 48–52 on Button/input/toggle) |
| Dynamic type / large text / narrow / landscape | M device + automated a11y scanner (deferred to pilot) |
| VoiceOver / TalkBack | M device (harness) — **not** claimed as run |
