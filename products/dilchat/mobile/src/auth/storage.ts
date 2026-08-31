/**
 * Secure credential storage. Tokens live ONLY in the platform secure store
 * (Keychain / Keystore) via expo-secure-store — never in AsyncStorage, logs,
 * analytics, or crash reports. `clearAll` wipes everything on sign-out or
 * account switch.
 *
 * RESILIENCE: reads NEVER throw. A locked/corrupt/unavailable keychain, or a
 * malformed stored value, is treated as "no credential" rather than crashing the
 * launch or trapping the app in a permanent loading state. Callers get `null`.
 */
import * as SecureStore from "expo-secure-store";

const ACCESS_KEY = "dilchat.access_token";
const REFRESH_KEY = "dilchat.refresh_token";

/**
 * Keep credentials on THIS device only: excluded from encrypted device backups
 * and from Keychain iCloud sync, so tokens can never be restored onto another
 * device. Requires the device to be unlocked to read them.
 */
const SECURE_OPTS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

/** A stored token is usable only if it is a non-empty, whitespace-free string. */
function sanitizeToken(v: string | null): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  if (t.length === 0) return null;
  // A well-formed JWT/opaque token contains no whitespace; reject a corrupted value.
  if (/\s/.test(t)) return null;
  return t;
}

export async function saveTokens(t: StoredTokens): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_KEY, t.accessToken, SECURE_OPTS);
  await SecureStore.setItemAsync(REFRESH_KEY, t.refreshToken, SECURE_OPTS);
}

async function readSanitized(key: string): Promise<string | null> {
  try {
    return sanitizeToken(await SecureStore.getItemAsync(key));
  } catch {
    // Keychain locked / unavailable / decryption error → treat as no credential.
    return null;
  }
}

export async function getAccessToken(): Promise<string | null> {
  return readSanitized(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return readSanitized(REFRESH_KEY);
}

/** True when a usable refresh credential is present. Never throws. */
export async function hasSession(): Promise<boolean> {
  return (await getRefreshToken()) !== null;
}

/** Remove all stored credentials (sign-out / account switch). Best-effort; never throws. */
export async function clearAll(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(ACCESS_KEY);
  } catch {
    /* ignore */
  }
  try {
    await SecureStore.deleteItemAsync(REFRESH_KEY);
  } catch {
    /* ignore */
  }
}
