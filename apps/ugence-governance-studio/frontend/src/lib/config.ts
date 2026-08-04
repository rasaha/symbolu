// Runtime configuration (§27). The API base URL is configured at build/deploy
// time via an environment variable ONLY — never from user input or arbitrary URLs.
// A strict allowlist of URL shapes prevents pointing the client at an unexpected
// host at runtime.

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

export const SUPPORTED_API_CONTRACT = "governance_studio.api.v1";

function sanitizeBaseUrl(raw: string | undefined): string {
  const candidate = (raw ?? DEFAULT_BASE_URL).trim().replace(/\/+$/, "");
  let url: URL;
  try {
    url = new URL(candidate);
  } catch {
    return DEFAULT_BASE_URL;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return DEFAULT_BASE_URL;
  }
  return candidate;
}

export const apiBaseUrl: string = sanitizeBaseUrl(
  (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_BASE_URL,
);
