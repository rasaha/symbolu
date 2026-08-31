/**
 * DILCHAT-D3C-M2 gating for push registration:
 * config-gated acquisition, prompt-at-most-once, silent degradation to
 * REST/polling, and a push token that never leaks into logs.
 */

import type { HttpClient } from "@/api/client";
// jest.mock calls are hoisted above this import, and the mock factories only
// close over the mock* variables lazily, so mocking is in place before the
// module under test (or its lazy expo-notifications import) loads.
import { maybeRegisterForPush, resetPromptGuardForTests } from "@/push/registration";

let mockExtra: Record<string, unknown> = {};
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: {
    get expoConfig() {
      return { extra: mockExtra };
    },
  },
}));

const mockGetPermissions = jest.fn();
const mockRequestPermissions = jest.fn();
const mockGetToken = jest.fn();
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: (...a: unknown[]) => mockGetPermissions(...a),
  requestPermissionsAsync: (...a: unknown[]) => mockRequestPermissions(...a),
  getExpoPushTokenAsync: (...a: unknown[]) => mockGetToken(...a),
}));

const SECRET_TOKEN = "ExponentPushToken[very-secret-token]";

function fakeClient(): { client: HttpClient; post: jest.Mock } {
  const post = jest.fn().mockResolvedValue({
    device_id: "d1",
    platform: "IOS",
    status: "ACTIVE",
    created_at: "x",
    revoked_at: null,
  });
  return { client: { post } as unknown as HttpClient, post };
}

describe("maybeRegisterForPush", () => {
  beforeEach(() => {
    mockExtra = { eas: { projectId: "test-project-id" } };
    mockGetPermissions.mockReset().mockResolvedValue({ status: "granted" });
    mockRequestPermissions.mockReset().mockResolvedValue({ status: "granted" });
    mockGetToken.mockReset().mockResolvedValue({ data: SECRET_TOKEN });
    resetPromptGuardForTests();
  });

  it("without an EAS project id: no acquisition attempt, no registration, no failure", async () => {
    mockExtra = {};
    const { client, post } = fakeClient();
    await expect(maybeRegisterForPush(client)).resolves.toBe("skipped_no_config");
    expect(mockGetPermissions).not.toHaveBeenCalled();
    expect(mockRequestPermissions).not.toHaveBeenCalled();
    expect(mockGetToken).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
  });

  it("registers when configured and permission is granted", async () => {
    const { client, post } = fakeClient();
    await expect(maybeRegisterForPush(client)).resolves.toBe("registered");
    expect(mockGetToken).toHaveBeenCalledWith({ projectId: "test-project-id" });
    expect(post).toHaveBeenCalledTimes(1);
    const [path, body] = post.mock.calls[0];
    expect(path).toBe("/v1/devices");
    expect(body).toEqual({ push_token: SECRET_TOKEN, platform: expect.any(String) });
  });

  it("a declined user is never re-prompted", async () => {
    mockGetPermissions.mockResolvedValue({ status: "denied" });
    const { client, post } = fakeClient();
    await expect(maybeRegisterForPush(client)).resolves.toBe("skipped_permission");
    await expect(maybeRegisterForPush(client)).resolves.toBe("skipped_permission");
    expect(mockRequestPermissions).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
  });

  it("prompts at most once per launch when undetermined", async () => {
    mockGetPermissions.mockResolvedValue({ status: "undetermined" });
    mockRequestPermissions.mockResolvedValue({ status: "denied" });
    const { client } = fakeClient();
    await expect(maybeRegisterForPush(client)).resolves.toBe("skipped_permission");
    await expect(maybeRegisterForPush(client)).resolves.toBe("skipped_permission");
    expect(mockRequestPermissions).toHaveBeenCalledTimes(1); // once, ever, this launch
  });

  it("an accepted prompt proceeds straight to registration", async () => {
    mockGetPermissions.mockResolvedValue({ status: "undetermined" });
    mockRequestPermissions.mockResolvedValue({ status: "granted" });
    const { client, post } = fakeClient();
    await expect(maybeRegisterForPush(client)).resolves.toBe("registered");
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("acquisition or registration failure degrades silently and never logs the token", async () => {
    const logSpy = jest.spyOn(console, "log").mockImplementation(() => undefined);
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    const errSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      mockGetToken.mockRejectedValue(new Error(SECRET_TOKEN));
      const { client } = fakeClient();
      await expect(maybeRegisterForPush(client)).resolves.toBe("failed_transport");

      mockGetToken.mockResolvedValue({ data: SECRET_TOKEN });
      const failing = fakeClient();
      failing.post.mockRejectedValue(new Error("http 503"));
      await expect(maybeRegisterForPush(failing.client)).resolves.toBe("failed_transport");

      for (const spy of [logSpy, warnSpy, errSpy]) {
        for (const call of spy.mock.calls) {
          expect(JSON.stringify(call)).not.toContain(SECRET_TOKEN);
        }
      }
    } finally {
      logSpy.mockRestore();
      warnSpy.mockRestore();
      errSpy.mockRestore();
    }
  });
});
