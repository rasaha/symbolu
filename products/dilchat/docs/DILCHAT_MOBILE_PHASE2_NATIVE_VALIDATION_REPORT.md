# DilChat Mobile — Phase 2 Track A: Native & Platform Build Validation

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com

Track A validates native Android/iOS generation, compilation, emulator/simulator
launch, installed-app custom-scheme deep links, lifecycle, privacy, and native
configuration. It deliberately does **not** implement the app-not-installed HTTPS
invitation flow (Track B) or the physical two-device pilot (Track C).

## 1. Host / capability inventory (authoritative)

| Capability | Value |
|---|---|
| OS / arch | Linux `6.18.x` x86_64 |
| RAM / disk | 15 GiB / ~29 GiB free |
| Node / npm | 22.22.2 / 10.9.7 |
| JDK (local) | Temurin/OpenJDK **21** (`JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`) |
| Gradle (local) | 8.14.3 |
| Android SDK (local) | **absent** — install **blocked**: org egress policy denies `dl.google.com:443` (proxy 403 to CONNECT); no `sdkmanager`/`adb`/platform/build-tools |
| Hardware virtualization | **`/dev/kvm` absent** → an Android emulator cannot boot here |
| macOS / Xcode | **absent** (Linux host) |

**Consequences (not fabricated):**
- Local Gradle compilation is **not executable** (SDK + Android Gradle Plugin +
  platform artifacts all come from the blocked `dl.google.com`). Per the sandbox
  policy this host must **not** be routed around; the compiled build is instead
  run in CI on GitHub's runner, which has the official Google SDK preinstalled.
- The Android **emulator** is **not executable** (no `/dev/kvm`).
- **All iOS** steps are **`NOT_EXECUTABLE_ON_THIS_HOST`** (no macOS/Xcode).

## 2. Baseline (re-verified at the Track A head)

`npm test` → **127/127 tests, 19 suites, exit 0** · lint 0 · tsc 0 · endpoint /
config / native-manifest guards OK · Metro export OK · no `android/`|`ios/` dir is
tracked in git. (Full automated/live-integration reproduction is recorded in
`DILCHAT_MOBILE_PHASE2_MERGE_AUDIT.md`.)

## 3. Android native generation — PASS (executed locally)

`npx expo prebuild --platform android --no-install` → exit 0. The generated
`AndroidManifest.xml` was inspected directly:

| Property | Value | Status |
|---|---|---|
| `applicationId` / `namespace` | `com.ugence.dilchat` | ✅ |
| App label | `DilChat` | ✅ |
| `versionCode` / `versionName` | `1` / `0.1.0` | ✅ |
| minSdk / compileSdk / targetSdk | 23 / 34 / 34 | ✅ (Expo SDK 51 compatible) |
| Permissions | `INTERNET` only; `READ/WRITE_EXTERNAL_STORAGE`, `SYSTEM_ALERT_WINDOW`, `VIBRATE` all `tools:node="remove"` | ✅ minimal |
| `allowBackup` | `false` | ✅ |
| Cleartext opt-in | none (`usesCleartextTraffic` absent) | ✅ |
| Deep-link intent filter | `MainActivity` (`exported=true`, `singleTask`, `portrait`) with `VIEW`+`DEFAULT`+`BROWSABLE`, `android:scheme="dilchat"` (and the Expo-default `com.ugence.dilchat` scheme) | ✅ custom scheme only; **no `https` App Links** (Track B correctly absent) |
| Other exported components | `DevSettingsActivity` `exported="false"` | ✅ |
| Leak scan of generated tree | no token / endpoint / `localhost` / local path / secret | ✅ |

No native-config defect found; the generated manifest matches the hardened Phase 2
posture and the `check:native` guard. `package.json`/`package-lock.json` (which
`expo prebuild` rewrites) were restored; the generated `android/` dir was removed;
the working tree is clean.

**`ANDROID_NATIVE_GENERATION_PASS`.**

## 4. Android compiled build — executed in CI (official Google SDK)

Because the local sandbox cannot download the SDK, a new CI job **`android-build`**
(`.github/workflows/dilchat-mobile-ci.yml`) runs the real compile on GitHub's
`ubuntu-latest` runner: Expo prebuild → manifest hardening guard →
`./gradlew --no-daemon assembleDebug` → debug-APK sanity. JDK 17 (RN 0.74 / Expo
SDK 51 target), least-privilege (`contents: read`), `pipefail`, no
`continue-on-error`, no signing/credentials/emulator/deploy, `android/` not
committed.

| Classification | Result |
|---|---|
| `ANDROID_GRADLE_DEBUG_BUILD_PASS` | **PASS** (deterministic) — `android-build` job **green** on head `c5bcee1f` (run `30987083271`, ~6.8 min compile). `./gradlew --no-daemon assembleDebug` on JDK 17.0.19 (Temurin) produced `app/build/outputs/apk/debug/app-debug.apk` (≈142 MB); manifest hardening guard + APK sanity passed. First observed green on head `3a3fc2c6`. |

### 4.1 Defect found & fixed during Track A — Gradle heap OOM (reproducibility)

The `assembleDebug` step **intermittently** failed with
`java.lang.OutOfMemoryError: Java heap space` inside the Hermes AAR
`JetifyTransform`: Expo's generated `android/gradle.properties` defaults to
`-Xmx2048m`, marginal for that transform on a loaded runner (it passed on one
head and OOM'd on the next with identical inputs). **Fix:** the job now appends
`org.gradle.jvmargs=-Xmx4g …` to the generated `gradle.properties` after prebuild
(later keys win), making the compile deterministic. Severity: medium (flaky gate);
in Track A scope (Gradle reproducibility). Config-only; no app/native source
changed. Re-verified green across a full compile on head `c5bcee1f`.

> Note: a one-off `integration` job failure on head `bb3b2537` (8/9 API calls
> erroring after `/v1/health` passed) was a **transient** backend/DB hiccup — the
> job passed on the four surrounding heads with identical inputs and again on the
> re-run at `c5bcee1f`. No code or harness change was required.
| `ANDROID_RELEASE_LIKE_COMPILE` | **bounded — not run.** `assembleRelease` requires a release `signingConfig`; production signing is explicitly out of Track A scope. A debug-signed release compile is deferred to the device/signing track. |

## 5. NOT executable on this host (recorded, not fabricated)

| Gate | Status | Reason |
|---|---|---|
| `ANDROID_EMULATOR_BOOT/LAUNCH`, `ANDROID_APK_INSTALL`, `ANDROID_BACKGROUND_RESUME`, `ANDROID_APP_SWITCHER_PRIVACY` (on-device) | `NOT_EXECUTABLE` | no `/dev/kvm`; no local SDK/emulator; a CI emulator job is not in Track A's permitted CI additions |
| `ANDROID_INSTALLED_APP_DEEP_LINK` (adb launch) | `NOT_EXECUTABLE` | requires a booted emulator/device. The deep-link *behavior* it would exercise is covered by 32 parser/router unit tests (consent-gated, single-accept, fail-closed on malformed/version/scheme/host/fragment/route) |
| iOS native generation, simulator build/launch, installed-app deep link, lifecycle, app-switcher privacy, a11y | `NOT_EXECUTABLE_ON_THIS_HOST` | Linux host, no macOS/Xcode — **not claimed, not fabricated** |
| `ANDROID_APP_NOT_INSTALLED_FALLBACK` | `NOT_IN_TRACK_A` | Track B |
| `IOS_APP_NOT_INSTALLED_FALLBACK` | `NOT_IN_TRACK_A` | Track B |

## 6. Handoff for a capable host (Track A completion)

To finish Track A, run on hosts that satisfy the missing capabilities:

**Android emulator / installed-app deep link (Linux+KVM or macOS):**
```
cd products/dilchat/mobile && npm ci
npx expo prebuild --platform android --no-install
# create + boot an AVD (API 34, x86_64) with hardware acceleration, then:
(cd android && ./gradlew --no-daemon assembleDebug)
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p com.ugence.dilchat 1        # launch
adb shell am start -a android.intent.action.VIEW \
  -d 'dilchat://invitation?v=1&token=<synthetic-64-char-urlsafe-token>' com.ugence.dilchat
# verify: opens only the invitation-review/consent flow (never auto-accept);
# malformed/unsupported-version/unknown-path/http/unknown-scheme fail closed;
# background/resume restores; app-switcher shield covers sensitive screens;
# `adb logcat` contains no token. Capture privacy-safe screenshots only.
```

**iOS (macOS + Xcode required):**
```
cd products/dilchat/mobile && npm ci
npx expo prebuild --platform ios --no-install
(cd ios && pod install)
xcodebuild -workspace ios/DilChat.xcworkspace -scheme DilChat \
  -sdk iphonesimulator -configuration Debug -derivedDataPath build build
xcrun simctl boot "iPhone 15" && xcrun simctl install booted <app>.app
xcrun simctl launch booted com.ugence.dilchat
xcrun simctl openurl booted 'dilchat://invitation?v=1&token=<synthetic-token>'
# verify Info.plist scheme, no unneeded usage strings, Keychain accessibility,
# ITSAppUsesNonExemptEncryption=false, associated domains ABSENT (Track B),
# background/resume, app-switcher shield; simulator log contains no token.
```

Use synthetic accounts and synthetic birth data only; never capture tokens or
private birth values.

## 7. Track A verdict

The three defined Track A advancing verdicts require the Android **emulator** and
the **iOS simulator**, both of which are **physically not executable on this
host** (`/dev/kvm` absent; not macOS). Therefore:

- `MOBILE_PHASE2_NATIVE_VALIDATION_COMPLETE` — **not** attainable here.
- `MOBILE_PHASE2_ANDROID_VALIDATED_IOS_PENDING` — **not** used: its Android
  *emulator* precondition is unmet (only native generation + compiled build are
  achievable here).
- `MOBILE_PHASE2_NATIVE_VALIDATION_BLOCKED` — **not** used: no native
  build/launch/privacy/lifecycle/storage/deep-link **defect** was found; the
  blockers are host/egress limitations, not defects.

**Track A outcome (this host): environment-limited.** Android native generation
and the Android Gradle **debug compile** are validated (the latter in CI on the
official Google SDK); the Android emulator + installed-app launch and **all** iOS
gates are `NOT_EXECUTABLE` here and are handed off (§6).

**Overall Phase 2 verdict remains `MOBILE_PHASE2_IMPLEMENTED_VALIDATION_PENDING`**
— now with an added, CI-verified Android compiled-build gate. It does **not**
advance to `MOBILE_PHASE2_DEVICE_PILOT_READY_WITH_LIMITATIONS`, which requires the
emulator/simulator launch + deep-link + privacy/lifecycle evidence that this host
cannot produce.

## 8. Confirmations

- **No** Track B HTTPS invitation infrastructure implemented.
- **No** physical-device pilot claimed (Track C).
- **No** Friends Finder, secure chat, AI Assist, Guna/Moon runtime, or exposed
  compatibility score.
- **No** production signing, credentials, deployment, or app-store submission.
- Synthetic data only; no tokens/PII in logs or artifacts. PR #1343 remains open
  and unmerged.
