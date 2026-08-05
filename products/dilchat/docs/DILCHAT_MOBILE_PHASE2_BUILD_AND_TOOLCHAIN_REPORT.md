# DilChat Mobile — Phase 2 Build & Toolchain Report

Environment: **Linux x86_64**, **Node v22.22.2**, **npm 10.9.7**, Python 3.12.3
(backend venv). Expo SDK **51.0.28** (`@expo/cli` 0.18.29), React Native **0.74.5**,
React **18.2.0**, `expo-router` 3.5.23, `expo-secure-store` 13.0.2,
`expo-linking` **6.3.1 (added)**, `ajv` **8.20.0 (via added devDependency `^8.17.1`)**.

## 1. Workstream A — the Expo toolchain failure (RESOLVED)

### Root cause (traced, not assumed)
`expo-router → schema-utils@4.3.3 → ajv-keywords@5.1.0` requires **ajv v8** (it
imports `ajv/dist/compile/codegen`). `eslint@8.57` depends on **ajv `^6`**, and npm
**hoisted `ajv@6.15.0` to the top** of `node_modules`, shadowing ajv v8 for
`ajv-keywords`. `npm ls ajv` flagged it `invalid: "^8.8.2"`. Direct reproduction:

```
$ node -e "require('ajv-keywords')(new (require('ajv'))())"
Error: Cannot find module 'ajv/dist/compile/codegen'
  node_modules/ajv-keywords/dist/definitions/typeof.js → …/ajv-keywords/dist/index.js
```

ajv v6 ships `lib/` (no `dist/compile/codegen`); ajv v8 ships the compiled `dist/`
(the "TypeScript-source resolution path"). This crashed **`expo config`**,
**`expo-doctor`**, and **`expo export`** (all run schema-utils validation).

### Fix (supported dependency config; no `node_modules` patch, no forced SDK bump)
- Added a **direct devDependency `ajv: ^8.17.1`** → ajv **8.20.0** hoists to the
  top; eslint transparently nests its own `ajv@6.15.0` under
  `node_modules/eslint/node_modules/ajv`. Both consumers are satisfied; `npm ls ajv`
  is clean.
- Rejected the alternative `overrides: { ajv: 8 }` — it forced ajv v8 onto eslint
  and **broke `npm run lint`**. Documented in `package.json` `//dependency-notes`.
- Added missing peer dependency **`expo-linking@6.3.1`** (SDK 51 pin; required by
  `expo-router`, and used by the deep-link interceptor).

### Verified gates
| Gate | Command | Result |
|------|---------|--------|
| Deterministic install | `npm ci` | exit 0, 1394 packages |
| Lint | `npm run lint` | 0 warnings |
| Strict types | `npm run typecheck` (`tsc --noEmit`) | 0 errors |
| Unit/component | `npm test` | **122 tests / 19 suites** passed |
| **Expo config** | `npx expo config --json --full` | **exit 0** (previously crashed) |
| **Metro export** | `npx expo export --platform android` | **exit 0**, 873 modules, 2.26 MB Hermes bundle |
| Expo doctor | `npx expo-doctor` | **14/17** pass (see §1.1) |
| Config guard | `npm run check:config` | OK |
| Endpoint guard | `npm run check:endpoint` | OK |

### 1.1 expo-doctor residual (network-blocked, not a code defect)
3 of 17 checks fail — the "Expo config schema", "native module versions", and
"packages match SDK" checks. All three fetch `api.expo.dev`, which the environment
network policy blocks (`curl https://api.expo.dev` → proxy **403**; npm registry is
allowlisted, Expo's API is not). The failure surfaces as
`SyntaxError: Unexpected token 'H', "Host not i"…` (an HTML "Host not in allowlist"
response parsed as JSON). These are **deferred** to a network-enabled runner, not
fixable in code.

### 1.2 Bundle safety (Metro export inspected)
The Hermes bundle embeds **no** `/home/…` absolute path, **no** production endpoint,
**no** `localhost` literal (the dev fallback is behind `__DEV__`, stripped in
export), and **no** secret. `react`/`react-native` are **single deduped copies**
(no duplicate runtime).

## 2. Workstream B — native project & build validation

### Architecture decision: **managed workflow / Continuous Native Generation (CNG)**
No `ios/` or `android/` directories are committed (both are `.gitignore`d). Native
projects are generated on demand by `expo prebuild` / EAS. This is the least
disruptive supported path; **generated native dirs are NOT committed** (repo
policy). See `DILCHAT_DECISION_LOG.md` DEC-M2-1.

### Android — verified via `expo prebuild --platform android` (exit 0)
The generated `android/app/src/main/AndroidManifest.xml` was inspected and hardened
in `app.config.js`:

- **Deep-link intent filter present:** `<data android:scheme="dilchat"/>` (and
  `com.ugence.dilchat`) on a `singleTask` `MainActivity` — invitation links are
  delivered to the app.
- **Permissions minimized:** the RN/Expo template's `READ_EXTERNAL_STORAGE`,
  `WRITE_EXTERNAL_STORAGE`, `SYSTEM_ALERT_WINDOW`, and `VIBRATE` are **blocked**
  (`android.blockedPermissions`), leaving only **`INTERNET`**. Re-running prebuild
  confirmed they carry `tools:node="remove"` in the merged manifest.
- **Backup disabled:** `android:allowBackup="false"` (defense in depth; auth tokens
  are already Keystore-only and device-only).
- **No cleartext:** no `usesCleartextTraffic="true"`; on Android 9+ cleartext is
  off by default, so a release build permits no cleartext production traffic. The
  `localhost` dev fallback is development-only.
- **App identity:** label `DilChat`, package `com.ugence.dilchat`, version `0.1.0`,
  portrait, `userInterfaceStyle: light`.

**Not run (deferred):** compiled `gradle assembleDebug/Release` and emulator install
— **no Android SDK/emulator** in this environment. See Known Limitations.

### iOS — configuration validated; build deferred
Resolved iOS config: `bundleIdentifier com.ugence.dilchat`, `supportsTablet`,
`infoPlist.ITSAppUsesNonExemptEncryption=false`. Keychain accessibility is set in
code (`expo-secure-store` `WHEN_UNLOCKED_THIS_DEVICE_ONLY`). **No iOS build was
attempted** — this is Linux, with no macOS/Xcode; iOS success is **not fabricated**.
URL scheme (`dilchat`) and privacy posture are validated via the resolved config.

## 3. Dependencies changed

| Package | Change | Reason |
|---------|--------|--------|
| `ajv` | **+ devDependency `^8.17.1`** (resolves 8.20.0) | Hoist ajv v8 for `ajv-keywords`; fixes the toolchain crash. |
| `expo-linking` | **+ dependency `6.3.1`** | Required peer of `expo-router`; deep-link interceptor. |

`package-lock.json` regenerated; `npm ci` reproducible. No other runtime dependency
versions changed; Expo/React/React-Native **not** upgraded.

## 4. Security & dependency review

`npm audit` reports **33 advisories** (1 critical, 19 high, 12 moderate, 1 low). See
`DILCHAT_MOBILE_PHASE2_KNOWN_LIMITATIONS.md` §Security for the per-advisory
classification. Summary: **all** trace to **build/CLI/dev tooling** (`@expo/cli`,
`@expo/prebuild-config`, `@expo/metro-config`, `@remix-run/*` dev server,
`postcss`, `turbo-stream`, `tar`, `@react-native-community/cli*`, `xcode`,
`@xmldom/xmldom`, `fast-xml-parser`, `jest-expo`) — **none on the on-device runtime
path**. The exported Hermes bundle contains none of `@remix-run`, `postcss`,
`@expo/cli`, `prebuild`, `turbo-stream`, or `xcode`. Remediation requires an Expo
SDK upgrade (out of Phase 2's bounded scope). `npm audit fix --force` was **not**
run.
