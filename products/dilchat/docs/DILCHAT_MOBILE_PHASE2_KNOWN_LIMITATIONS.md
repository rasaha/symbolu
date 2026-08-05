# DilChat Mobile — Phase 2 Known Limitations

Everything below is explicitly **outside** what the current environment can execute
or **outside Phase 2 merge scope**. Nothing here is fabricated as passing.

## 1. Deferred — environment cannot execute (report as PENDING, not PASS)

| Item | Why deferred | Evidence |
|---|---|---|
| Android **compiled build** (`gradle assembleDebug/Release`) | No Android SDK/NDK/emulator in this Linux CI | `expo prebuild` succeeds and the manifest is validated; gradle not present |
| Android **emulator** run | No emulator/AVD available | — |
| **iOS** resolved-config-beyond, simulator build, Xcode | Linux host, no macOS/Xcode | iOS config validated via `expo config`; build **not** attempted (not fabricated) |
| **Physical-device** two-device pilot | No devices attached | Harness ready: `DILCHAT_MOBILE_PHASE2_DEVICE_TEST_PLAN.md` |
| VoiceOver / TalkBack, dynamic-type/landscape on-device | Requires a device/simulator | Automated a11y (roles/labels/announcements) passes; on-device deferred |
| `expo-doctor` 3/17 checks (config-schema, native-module-versions, SDK-match) | Fetch `api.expo.dev` → proxy **403** ("Host not in allowlist") | 14/17 pass; the 3 are network-blocked, not code defects |
| Universal (HTTPS) invitation links | No production host in Phase 2 | Custom `dilchat://` scheme implemented + manifest-verified; HTTPS host allowlist (`extra.invitationLinkHosts`) is empty by design |

## 2. Out of Phase 2 scope (by requirement)

Secure partner chat, messaging, notifications with content, AI Assist, conversation
preference learning, Moon receptivity, Guna/Koota/Dosha/Parihara execution,
compatibility scoring, payments, production credentials, app-store signing/release,
and public deployment. Guna rule pack remains **non-executable**. These belong to
Phase 3 (secure chat) and Phase 4A–4D (AI Assist), and were **not** implemented.

## 3. Security / dependency advisories (`npm audit` — traced, not waved away)

`npm audit` → **33 advisories** (1 critical · 19 high · 12 moderate · 1 low). Every
advisory is on the **build / CLI / dev-tooling** path; **none** is on the on-device
runtime path. The exported Hermes bundle contains none of `@remix-run`, `postcss`,
`@expo/cli`, `prebuild-config`, `turbo-stream`, or `xcode`.

| Package | Sev | Path | Class | Exploitable here? | Remediation |
|---|---|---|---|---|---|
| `tar` | critical | `@expo/*`/prebuild extraction | build | No — no fs/tar in RN runtime | Expo SDK upgrade |
| `@expo/cli`, `@expo/config`, `@expo/config-plugins`, `@expo/metro-config`, `@expo/prebuild-config`, `@expo/plist` | high | Expo build/CLI | build | No — not in app bundle | Expo SDK upgrade |
| `@remix-run/node`, `@remix-run/server-runtime`, `turbo-stream` | high | expo-router **dev server** / static-render | build/dev | No — dev-only | expo-router upgrade (SDK) |
| `@xmldom/xmldom`, `fast-xml-parser`, `xcode`, `@expo/plist` | high/mod | native-project generation (prebuild) | build | No — prebuild-only | Expo SDK upgrade |
| `postcss`, `send` | high/low | webpack/dev-server tooling | build/dev | No — dev-only | tooling upgrade |
| `cacache` | high | npm/install tooling | build | No | tooling upgrade |
| `expo`, `expo-asset`, `expo-constants`, `expo-linking`, `expo-router`, `expo-splash-screen`, `react-native` | high/mod | flagged transitively via their **CLI/build** deps | build (runtime portions unaffected) | No — advisory is the tooling dep, not the on-device module | Expo SDK upgrade |
| `@react-native-community/cli*` | mod | RN CLI | build/dev | No — not in app bundle | SDK/CLI upgrade |
| `uuid` (<11.1.1) | mod | transitive | build/runtime-guarded | No — vuln needs a caller-supplied buffer arg; app never passes one | dep upgrade |
| `jest-expo` | high | test only | dev/test | No | SDK upgrade |

**Disposition:** all advisories are **build/dev-time**, off the runtime path, and
their fixes require an **Expo SDK upgrade** — deliberately **out of Phase 2's
bounded scope** (Phase 2 repaired the toolchain via a targeted `ajv` hoist rather
than bumping the SDK). `npm audit fix --force` was **not** run (prohibited). A
controlled Expo SDK 52/53 upgrade is the recommended follow-up to clear these.

## 4. Notes

- Backend was **not** modified in Phase 2; the backend regression suite was not
  re-run here (Phase 1 records ruff/mypy clean, pytest 201/0-skipped, single Alembic
  head). If any shared contract file changes in a later revision, re-run the backend
  suite.
- The exact Phase 2 verdict is **`MOBILE_PHASE2_IMPLEMENTED_VALIDATION_PENDING`**
  (see `DILCHAT_MOBILE_PHASE2_IMPLEMENTATION_REPORT.md`).
