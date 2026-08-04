import { clearAll, getAccessToken, getRefreshToken, hasSession, saveTokens } from "@/auth/storage";

// expo-secure-store is mocked with an in-memory store in jest.setup.ts and
// cleared before each test.
describe("auth storage", () => {
  it("has no session before any tokens are saved", async () => {
    expect(await hasSession()).toBe(false);
    expect(await getAccessToken()).toBeNull();
    expect(await getRefreshToken()).toBeNull();
  });

  it("saves and reads back tokens", async () => {
    await saveTokens({ accessToken: "access-abc", refreshToken: "refresh-xyz" });
    expect(await getAccessToken()).toBe("access-abc");
    expect(await getRefreshToken()).toBe("refresh-xyz");
    expect(await hasSession()).toBe(true);
  });

  it("clearAll wipes everything", async () => {
    await saveTokens({ accessToken: "a", refreshToken: "r" });
    await clearAll();
    expect(await getAccessToken()).toBeNull();
    expect(await getRefreshToken()).toBeNull();
    expect(await hasSession()).toBe(false);
  });
});
