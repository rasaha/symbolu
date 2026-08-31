/**
 * Runtime configuration. The API base URL comes ONLY from Expo config
 * (`extra.apiBaseUrl`, sourced from the `DILCHAT_API_BASE_URL` env var at build
 * time) — never a hardcoded production endpoint. In development it defaults to a
 * local backend. A production build must supply the URL via configuration.
 */
import Constants from "expo-constants";

const DEV_DEFAULT = "http://localhost:8080";

function readConfiguredBaseUrl(): string | undefined {
  const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, unknown>;
  const v = extra.apiBaseUrl;
  return typeof v === "string" && v.length > 0 ? v : undefined;
}

/** Resolved API base URL. Falls back to a LOCAL dev URL only in development. */
export function getApiBaseUrl(): string {
  const configured = readConfiguredBaseUrl();
  if (configured) return configured.replace(/\/+$/, "");
  if (__DEV__) return DEV_DEFAULT;
  throw new Error(
    "DILCHAT_API_BASE_URL is not configured. A non-development build must supply " +
      "the API base URL through Expo config (extra.apiBaseUrl); no endpoint is hardcoded.",
  );
}

/** Request timeout (ms). */
export const REQUEST_TIMEOUT_MS = 15000;

/**
 * HTTPS hosts allowed to carry an invitation universal/app link, sourced ONLY
 * from Expo config (`extra.invitationLinkHosts`). Empty by default: with no host
 * configured, HTTPS invitation links are rejected and only the app's own
 * `dilchat://` scheme is honored. This is the anti-open-redirect allowlist — a
 * link to any other host is never opened. Never a hardcoded production host.
 */
export function getTrustedInvitationLinkHosts(): string[] {
  const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, unknown>;
  const v = extra.invitationLinkHosts;
  if (!Array.isArray(v)) return [];
  return v.filter((h): h is string => typeof h === "string" && h.length > 0).map((h) => h.toLowerCase());
}
