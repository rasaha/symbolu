/**
 * Secure credential storage. Tokens live ONLY in the platform secure store
 * (Keychain / Keystore) via expo-secure-store — never in AsyncStorage, logs,
 * analytics, or crash reports. `clearAll` wipes everything on sign-out or
 * account switch.
 */
import * as SecureStore from "expo-secure-store";

const ACCESS_KEY = "dilchat.access_token";
const REFRESH_KEY = "dilchat.refresh_token";

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

export async function saveTokens(t: StoredTokens): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_KEY, t.accessToken);
  await SecureStore.setItemAsync(REFRESH_KEY, t.refreshToken);
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
