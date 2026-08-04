// Dynamic Expo config. The API base URL is injected from the environment at
// build time (DILCHAT_API_BASE_URL) and is NEVER hardcoded here. When unset,
// the app falls back to a LOCAL dev URL (see src/config/env.ts); a real build
// must supply DILCHAT_API_BASE_URL.
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
    ios: { supportsTablet: true, bundleIdentifier: "com.ugence.dilchat" },
    android: { package: "com.ugence.dilchat" },
    plugins: ["expo-router", "expo-secure-store"],
    extra: {
      apiBaseUrl: process.env.DILCHAT_API_BASE_URL || undefined,
      router: { origin: false },
    },
  },
});
