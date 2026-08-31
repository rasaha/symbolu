// Dynamic Expo config. The API base URL is injected from the environment at
// build time (DILCHAT_API_BASE_URL) and is NEVER hardcoded here. When unset,
// the app falls back to a LOCAL dev URL (see src/config/env.ts); a real build
// must supply DILCHAT_API_BASE_URL.
//
// Phase 2 hardening:
// - Android permissions are minimized: only INTERNET is needed. Expo/RN default
//   templates add READ/WRITE_EXTERNAL_STORAGE, SYSTEM_ALERT_WINDOW, and VIBRATE
//   which this app does not use — they are explicitly blocked.
// - Android auto-backup is disabled (defense in depth; auth tokens already live
//   in the Keystore via expo-secure-store with WHEN_UNLOCKED_THIS_DEVICE_ONLY,
//   excluded from backups/sync).
// - The `dilchat://` scheme powers invitation deep links (see src/deeplink). No
//   HTTPS universal-link host is configured in this phase (no production host);
//   `extra.invitationLinkHosts` is the allowlist and is intentionally empty.
module.exports = () => ({
  expo: {
    name: "DilChat",
    slug: "dilchat",
    version: "0.1.0",
    orientation: "portrait",
    scheme: "dilchat",
    userInterfaceStyle: "light",
    newArchEnabled: false,
    assetBundlePatterns: ["**/*"],
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.ugence.dilchat",
      // No cleartext exception; a real build talks to the configured HTTPS API.
      infoPlist: {
        ITSAppUsesNonExemptEncryption: false,
      },
    },
    android: {
      package: "com.ugence.dilchat",
      allowBackup: false,
      // Minimal permission set — remove unused defaults added by the RN/Expo template.
      blockedPermissions: [
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.VIBRATE",
      ],
    },
    plugins: ["expo-router", "expo-secure-store"],
    extra: {
      apiBaseUrl: process.env.DILCHAT_API_BASE_URL || undefined,
      // HTTPS hosts allowed to carry an invitation universal link. Empty in this
      // phase: only the app's own dilchat:// scheme is honored (anti open-redirect).
      invitationLinkHosts: [],
      router: { origin: false },
    },
  },
});
