// Dynamic Expo config. The API base URL is injected from the environment at
// build time (DILCHAT_API_BASE_URL) and is NEVER hardcoded here. When unset,
// the app falls back to a LOCAL dev URL (see src/config/env.ts); a real build
// must supply DILCHAT_API_BASE_URL.
//
// Phase 2 hardening (amended by DILCHAT-D3C-M1):
// - Android permissions stay minimized to what the ratified feature set
//   demonstrably requires. Phase 3C adds expo-notifications for the approved
//   content-free push capability, which brings POST_NOTIFICATIONS on supported
//   Android versions. Unrelated Expo/RN template permissions
//   (READ/WRITE_EXTERNAL_STORAGE, SYSTEM_ALERT_WINDOW) remain blocked, and
//   VIBRATE stays blocked: the pinned expo-notifications build functions
//   without it and least privilege governs (see scripts/check-native-android.sh,
//   which pins the expected generated-manifest permission set).
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
    plugins: ["expo-router", "expo-secure-store", "expo-notifications"],
    extra: {
      apiBaseUrl: process.env.DILCHAT_API_BASE_URL || undefined,
      // EAS project id: deployment configuration for Expo push-token
      // acquisition (DILCHAT-D3C-M2). Absent => the app NEVER attempts token
      // acquisition and runs on REST + polling alone. Never hardcoded.
      eas: process.env.DILCHAT_EAS_PROJECT_ID
        ? { projectId: process.env.DILCHAT_EAS_PROJECT_ID }
        : undefined,
      // HTTPS hosts allowed to carry an invitation universal link. Empty in this
      // phase: only the app's own dilchat:// scheme is honored (anti open-redirect).
      invitationLinkHosts: [],
      router: { origin: false },
    },
  },
});
