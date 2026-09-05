import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider, useAuth } from "@/auth/AuthContext";
import {
  __resetPendingInvitationForTests,
  getPendingInvitation,
  setPendingInvitation,
} from "@/invitation/pendingInvitation";

// Mock the network endpoints so no real backend is needed. Names are `mock`-
// prefixed so the jest.mock factory may reference them.
const mockLogin = jest.fn();
const mockLogout = jest.fn();
const mockLogoutAll = jest.fn();
jest.mock("@/api/endpoints", () => ({
  AuthApi: {
    login: (...a: unknown[]) => mockLogin(...a),
    logout: (...a: unknown[]) => mockLogout(...a),
    logoutAll: (...a: unknown[]) => mockLogoutAll(...a),
    register: jest.fn(),
    refresh: jest.fn(),
  },
}));

const TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-ab";

function Harness({ onReady }: { onReady: (v: ReturnType<typeof useAuth>) => void }): React.ReactElement {
  const auth = useAuth();
  onReady(auth);
  return <Text>{auth.status}</Text>;
}

function renderAuth() {
  const qc = new QueryClient();
  let latest!: ReturnType<typeof useAuth>;
  const utils = render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <Harness onReady={(v) => (latest = v)} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { qc, get: () => latest, ...utils };
}

describe("AuthContext — cross-account isolation & pending cleanup", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockLogout.mockReset();
    mockLogoutAll.mockReset();
    __resetPendingInvitationForTests();
  });

  it("clears the query cache and pending invitation on sign-out", async () => {
    mockLogin.mockResolvedValue({ access_token: "a", refresh_token: "r", expires_in: 900 });
    mockLogout.mockResolvedValue(undefined);
    const { qc, get } = renderAuth();
    await waitFor(() => expect(get().status).toBe("signed-out"));

    // Sign in as account A, seed cached server state + a pending invitation.
    await act(async () => {
      await get().signIn("a@example.com", "pw");
    });
    qc.setQueryData(["me"], { id: "userA", email: "a@example.com" });
    setPendingInvitation({ token: TOKEN, version: 1 });
    expect(qc.getQueryData(["me"])).toBeTruthy();
    expect(getPendingInvitation()).not.toBeNull();

    // Sign out — everything account-scoped must be gone.
    await act(async () => {
      await get().signOut("device");
    });
    expect(qc.getQueryData(["me"])).toBeUndefined();
    expect(getPendingInvitation()).toBeNull();
    expect(get().status).toBe("signed-out");
  });

  it("does not carry account A's cached data into account B (switch clears cache)", async () => {
    mockLogin.mockResolvedValue({ access_token: "a", refresh_token: "r", expires_in: 900 });
    mockLogout.mockResolvedValue(undefined);
    const { qc, get } = renderAuth();
    await waitFor(() => expect(get().status).toBe("signed-out"));

    await act(async () => {
      await get().signIn("a@example.com", "pw");
    });
    qc.setQueryData(["me"], { id: "userA", email: "a@example.com" });

    await act(async () => {
      await get().signOut("device");
    });
    // Sign in as B: cache starts clean (signIn also clears), no A data leaks.
    await act(async () => {
      await get().signIn("b@example.com", "pw");
    });
    expect(qc.getQueryData(["me"])).toBeUndefined();
  });
});
