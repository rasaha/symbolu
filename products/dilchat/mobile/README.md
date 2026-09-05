# DilChat Mobile (Phase 1 + Phase 2 hardening + Phase 3D chat + Phase 3C push)

Account, birth-profile, partner-invitation, pairing, consent, and the minimal
1:1 partner chat — the DilChat mobile vertical slice, with Phase 2
device/deep-link/lifecycle/privacy/native hardening and the Phase 3C
config-gated push-registration slice.

> **This app provides account, profile, invitation, pairing, consent, and 1:1
> text chat only. Guna Milan and compatibility analysis remain blocked and
> unavailable.** The app shows no Guna score, Koota, compatibility report,
> astrology interpretation, daily guidance, or AI.

## Phase 3D — minimal 1:1 chat (`app/(app)/chat.tsx`, `src/chat/`)

A text-only chat over the merged Phase 3A secure-chat REST backend; the client
adds no backend surface and no realtime transport:

- **History** — forward cursor pagination (ascending `server_sequence`; cursors
  are opaque and server-minted), auto-paged to the tail, refreshed by
  react-query **polling** (`CHAT_POLL_MS`); no WebSocket. Push (Phase 3C) is
  advisory-only and never drives chat state.
- **Sends** — optimistic pending bubbles keyed by a generated
  `client_message_id` (`src/chat/clientMessageId.ts`); a failed send offers
  Retry/Discard, and Retry replays the **same** key so the backend's idempotency
  can never duplicate a message committed by a timed-out request.
- **Read state** — forward-only, pushed only for sequences actually loaded on
  screen; the backend ignores backward writes.
- **Tombstones** — a deleted message keeps its row and renders "Message
  deleted"; the client never shows a deleted body. (No delete UI this phase.)
- **No media, no group chat, no typing/presence.** Chat correctness never
  depends on push (see below): polling remains the delivery mechanism.

## Phase 3C — config-gated push registration (`src/push/registration.ts`)

An OPTIONAL delivery enhancement over the merged Phase 3C backend
(`/v1/devices` + outbox relay). Push availability never determines messaging
correctness — every failure path degrades silently to REST + polling.

- **Config gate** — token acquisition happens ONLY when an EAS project id is
  configured via `DILCHAT_EAS_PROJECT_ID` (→ `extra.eas.projectId`, never
  hardcoded; `scripts/check-config.js` fails a baked-in id). Without it the app
  never touches the push APIs and runs on polling alone (`skipped_no_config`,
  distinguishable from `failed_transport` without exposing tokens).
- **Permission** — requested at most once per launch, only from the OS
  "undetermined" state; a user who declined is never re-prompted. The
  permission covers content-free delivery notices only ("You have a new
  message." — the notification never carries names, message content, or
  relationship/astrology/safety information; that is the backend relay's
  contract).
- **Registration** — granted permission + acquired Expo token →
  authenticated `POST /v1/devices`. The push token is SENSITIVE: never
  logged, never displayed, never an authentication credential; logout
  revocation is the backend's contract.
- **Android permissions** — the generated app manifest stays pinned to
  `INTERNET` only (`scripts/check-native-android.sh`); `POST_NOTIFICATIONS`
  arrives from the expo-notifications library manifest at Gradle merge time
  per the DEC-3C-M1 amendment. Storage/overlay/VIBRATE stay blocked;
  `allowBackup=false` unchanged.

## Phase 2 hardening (device / deep-link / lifecycle / privacy / native)

- **Invitation deep links** — versioned, allowlisted `dilchat://invitation?v=1&token=…`
  links (`src/deeplink`, `src/invitation`). Only the invitation intent is honored
  (no open redirect / arbitrary route); context is preserved through
  authentication; a signed-in link routes to the **consent** screen (consent is
  never bypassed); the token is in-memory only and cleared on
  accept/reject/invalidate/sign-out/switch.
- **Session/lifecycle resilience** — single-flight refresh, resilient secure
  storage (never throws / no infinite loading), cross-account cache + pending
  clear.
- **Offline** — accept/unpair never blind-retry an ambiguous response; neutral
  recovery + refresh of authoritative server state.
- **Privacy** — app-switcher shield (`src/privacy`), device-only Keychain/Keystore
  tokens, Android backup off, minimized permissions (`INTERNET` only).
- **Toolchain** — the Expo SDK 51 `ajv-keywords` crash is fixed (`ajv@^8` hoist);
  `expo config` and Metro export run. See
  [`docs/DILCHAT_MOBILE_PHASE2_BUILD_AND_TOOLCHAIN_REPORT.md`](../docs/DILCHAT_MOBILE_PHASE2_BUILD_AND_TOOLCHAIN_REPORT.md).

See [`docs/DILCHAT_MOBILE_PHASE2_IMPLEMENTATION_REPORT.md`](../docs/DILCHAT_MOBILE_PHASE2_IMPLEMENTATION_REPORT.md)
and [`docs/DILCHAT_MOBILE_PHASE2_KNOWN_LIMITATIONS.md`](../docs/DILCHAT_MOBILE_PHASE2_KNOWN_LIMITATIONS.md).

Stack: **Expo SDK 51 · React Native 0.74 · TypeScript (strict) · Expo Router ·
@tanstack/react-query · expo-secure-store**. See
[`docs/DILCHAT_MOBILE_ARCHITECTURE.md`](../docs/DILCHAT_MOBILE_ARCHITECTURE.md),
[`docs/DILCHAT_MOBILE_API_CONTRACT_MAP.md`](../docs/DILCHAT_MOBILE_API_CONTRACT_MAP.md),
and [`docs/DILCHAT_MOBILE_SECURITY_AND_PRIVACY.md`](../docs/DILCHAT_MOBILE_SECURITY_AND_PRIVACY.md).

## Requirements

- Node **22+**, npm **10+**
- A running DilChat backend (see `products/dilchat/README.md`) for real device use
- iOS Simulator / Android Emulator / Expo Go for on-device runs (not needed for tests)

## Setup

```bash
cd products/dilchat/mobile
npm install                     # or: npm ci
cp .env.example .env            # then set DILCHAT_API_BASE_URL if not localhost
```

The API base URL is read from `DILCHAT_API_BASE_URL` (via `app.config.js` →
`extra.apiBaseUrl`). No production endpoint is hardcoded; in development it defaults
to `http://localhost:8080`.

## Run the backend (for real device use)

```bash
cd products/dilchat
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[test,dev,swiss]"
bash scripts/dev_db.sh                       # local PostgreSQL (dev only)
export DILCHAT_DATABASE_URL='postgresql+asyncpg://postgres@/dilchat_dev?host=/tmp&port=5433'
export DILCHAT_ENVIRONMENT=development
alembic upgrade head
uvicorn ugence_dilchat.app:create_app --factory --port 8080
```

## Run the app

```bash
cd products/dilchat/mobile
export DILCHAT_API_BASE_URL=http://localhost:8080     # Android emulator: http://10.0.2.2:8080
npx expo start                 # then press i (iOS), a (Android), or use Expo Go
```

## Quality commands (what CI runs)

```bash
cd products/dilchat/mobile
npm run lint                   # eslint (max-warnings 0)
npm run typecheck              # tsc --noEmit (strict)
npm test                       # jest (unit / component / contract)
npm run check:endpoint         # no hardcoded production endpoint
npm run check:contract         # API contract-drift (set DILCHAT_OPENAPI_JSON)
npm run check:config           # Expo config validation (shape + plugins + no baked endpoint)
```

Live backend integration (production client vs real FastAPI + PostgreSQL):

```bash
# starts a fresh migrated DB + uvicorn, runs the production client, tears down:
PYTHON=python BACKEND_DIR="$PWD/.." \
  DILCHAT_DATABASE_URL='postgresql+asyncpg://postgres@/dilchat_ci?host=/tmp&port=5433' \
  npm run test:integration
```

Contract-drift with a live backend:

```bash
# from products/dilchat, with the venv active:
python -m ugence_dilchat.scripts_openapi > /tmp/openapi.json
cd mobile && DILCHAT_OPENAPI_JSON=/tmp/openapi.json npm run check:contract
```

## Supported user journey

User A registers → creates their birth profile → creates an invitation → shares the
code. User B registers/sign-in → creates their birth profile → enters the code →
reads the consent screen → explicitly consents → both see the paired connection.
Neither can read the other's private birth-profile fields. Either party can unpair,
which revokes shared access immediately.

## Exclusions (Phase 1)

No Guna/Koota/compatibility, no astrology interpretation, no daily Moon guidance, no
transit UI, no chat, no AI coaching, no agreements, no notifications, no payments,
no deployment. A "Compatibility" screen exists that states only:
*"Compatibility analysis is not yet available."*

## Known limitations

- CI does not build device binaries or run a simulator (no emulator in CI); on-device
  runs are manual.
- Birthplace is entered manually (label + latitude/longitude + IANA time zone); no
  place-search yet. The device time zone is **not** assumed to be the birth zone.
