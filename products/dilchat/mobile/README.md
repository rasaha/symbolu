# DilChat Mobile (Phase 1)

Account, birth-profile, partner-invitation, pairing, and consent — the first
DilChat mobile vertical slice.

> **Phase 1 provides account, profile, invitation, pairing, and consent only.
> Guna Milan and compatibility analysis remain blocked and unavailable.** The app
> shows no Guna score, Koota, compatibility report, astrology interpretation,
> daily guidance, chat, or AI.

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
