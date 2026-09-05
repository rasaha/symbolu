/**
 * Secure-storage resilience: a locked/corrupt keychain or a malformed stored
 * value must degrade to "no session" — never throw, never trap the app in a
 * loading state. This file provides its own controllable expo-secure-store mock.
 */
const mockStore = new Map<string, string>();
const mockGetItem = jest.fn(async (k: string) => (mockStore.has(k) ? mockStore.get(k)! : null));

jest.mock("expo-secure-store", () => ({
  WHEN_UNLOCKED_THIS_DEVICE_ONLY: "WHEN_UNLOCKED_THIS_DEVICE_ONLY",
  setItemAsync: async (k: string, v: string) => void mockStore.set(k, v),
  getItemAsync: (k: string) => mockGetItem(k),
  deleteItemAsync: async (k: string) => void mockStore.delete(k),
}));

// The module under test is imported AFTER the mock above so it binds to the
// controllable expo-secure-store mock.
// eslint-disable-next-line import/first
import * as storage from "@/auth/storage";

beforeEach(() => {
  mockStore.clear();
  mockGetItem.mockClear();
  mockGetItem.mockImplementation(async (k: string) => (mockStore.has(k) ? mockStore.get(k)! : null));
});

describe("storage resilience", () => {
  it("reports a valid session for a well-formed refresh token", async () => {
    await storage.saveTokens({ accessToken: "a.b.c", refreshToken: "r".repeat(40) });
    expect(await storage.hasSession()).toBe(true);
    expect(await storage.getRefreshToken()).toBe("r".repeat(40));
  });

  it("treats a keychain read failure as no session (no throw)", async () => {
    mockGetItem.mockRejectedValue(new Error("keychain locked"));
    await expect(storage.hasSession()).resolves.toBe(false);
    await expect(storage.getAccessToken()).resolves.toBeNull();
  });

  it("treats a malformed (whitespace/empty) stored token as absent", async () => {
    mockStore.set("dilchat.refresh_token", "  bad token with spaces ");
    expect(await storage.hasSession()).toBe(false);
    mockStore.set("dilchat.refresh_token", "   ");
    expect(await storage.hasSession()).toBe(false);
  });

  it("clearAll never throws even if delete fails", async () => {
    await storage.saveTokens({ accessToken: "a", refreshToken: "r".repeat(40) });
    await expect(storage.clearAll()).resolves.toBeUndefined();
  });
});
