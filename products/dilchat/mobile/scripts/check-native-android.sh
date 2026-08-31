#!/usr/bin/env bash
#
# Generated-native-config guard (Android). Runs `expo prebuild` for Android in a
# throwaway working tree and asserts the merged AndroidManifest.xml matches the
# hardened Phase 2 posture:
#   - the dilchat:// deep-link intent filter is present;
#   - the app declares ONLY the INTERNET permission at runtime (the RN/Expo
#     template defaults READ/WRITE_EXTERNAL_STORAGE, SYSTEM_ALERT_WINDOW, VIBRATE
#     are removed via tools:node="remove");
#   - auto-backup is disabled (allowBackup="false");
#   - no cleartext-traffic opt-in is baked in.
#
# It does NOT compile an APK (no Android SDK required) — it validates the config
# that a native build would consume. The generated android/ dir is NOT committed;
# this guard regenerates and inspects it, then removes it.
set -euo pipefail

MOBILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MOBILE_DIR"

# `expo prebuild` rewrites a couple of package.json fields (the run scripts). Snapshot
# and restore package.json + package-lock.json so this guard leaves no diff.
PKG_BAK="$(mktemp)"; LOCK_BAK="$(mktemp)"
cp "$MOBILE_DIR/package.json" "$PKG_BAK"
cp "$MOBILE_DIR/package-lock.json" "$LOCK_BAK" 2>/dev/null || true
cleanup() {
  rm -rf "$MOBILE_DIR/android"
  cp "$PKG_BAK" "$MOBILE_DIR/package.json"
  cp "$LOCK_BAK" "$MOBILE_DIR/package-lock.json" 2>/dev/null || true
  rm -f "$PKG_BAK" "$LOCK_BAK"
}
trap cleanup EXIT

echo "check-native-android: expo prebuild --platform android"
rm -rf "$MOBILE_DIR/android"
EXPO_NO_TELEMETRY=1 CI=1 npx expo prebuild --platform android --no-install >/dev/null 2>&1

MANIFEST="$MOBILE_DIR/android/app/src/main/AndroidManifest.xml"
if [[ ! -f "$MANIFEST" ]]; then
  echo "check-native-android: FAIL — manifest not generated" >&2
  exit 1
fi

fail=0

# Deep-link intent filter for the app scheme.
if ! grep -q 'android:scheme="dilchat"' "$MANIFEST"; then
  echo "  FAIL: missing dilchat:// deep-link scheme in manifest" >&2; fail=1
fi

# Backup disabled.
if ! grep -q 'android:allowBackup="false"' "$MANIFEST"; then
  echo "  FAIL: allowBackup is not false" >&2; fail=1
fi

# Unused permissions must be removed (tools:node="remove"), not active.
for perm in READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE SYSTEM_ALERT_WINDOW VIBRATE; do
  # Active (non-removed) declaration of a blocked permission is a failure.
  if grep -E "android.permission.${perm}\"" "$MANIFEST" | grep -qv 'tools:node="remove"'; then
    echo "  FAIL: permission ${perm} is active (should be blocked)" >&2; fail=1
  fi
done

# INTERNET must be present (the app needs the network).
if ! grep -q 'android.permission.INTERNET' "$MANIFEST"; then
  echo "  FAIL: INTERNET permission missing" >&2; fail=1
fi

# No cleartext opt-in baked into the manifest.
if grep -q 'usesCleartextTraffic="true"' "$MANIFEST"; then
  echo "  FAIL: usesCleartextTraffic=true present (cleartext opt-in)" >&2; fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "check-native-android: FAILED" >&2
  exit 1
fi
echo "check-native-android: OK (deep-link scheme, minimal permissions, backup off, no cleartext)"
