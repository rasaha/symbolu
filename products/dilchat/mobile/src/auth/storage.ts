/**
 * Secure credential storage. Tokens live ONLY in the platform secure store
 * (Keychain / Keystore) via expo-secure-store — never in AsyncStorage, logs,
 * analytics, or crash reports. `clearAll` wipes everything on sign-out or
 * account switch.
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

export async function saveTokens(t: StoredTokens): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_KEY, t.accessToken, SECURE_OPTS);
  await SecureStore.setItemAsync(REFRESH_KEY, t.refreshToken, SECURE_OPTS);
}

export async function getAccessToken(): Promise<string | null> {
  return SecureStore.getItemAsync(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_KEY);
}

export async function hasSession(): Promise<boolean> {
  return (await getRefreshToken()) !== null;
}

/** Remove all stored credentials (sign-out / account switch). */
export async function clearAll(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}
