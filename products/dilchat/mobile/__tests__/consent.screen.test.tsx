import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import Consent from "../app/(app)/consent";
import { ApiError } from "@/api/errors";
import { __resetPendingInvitationForTests } from "@/invitation/pendingInvitation";

// A realistic invitation token (backend issues secrets.token_urlsafe(48) — 64
// URL-safe chars). The token validator rejects short/garbage input, so fixtures
// must look like real tokens.
const TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-ab";

const mockAccept = jest.fn();
const mockReplace = jest.fn();
const mockBack = jest.fn();

jest.mock("@/query/hooks", () => ({
  useAcceptInvitation: () => ({ mutateAsync: mockAccept, isPending: false }),
}));

jest.mock("expo-router", () => ({
  useRouter: () => ({ replace: mockReplace, back: mockBack, push: jest.fn() }),
  useLocalSearchParams: () => ({ token: TOKEN }),
}));

describe("Consent screen", () => {
  beforeEach(() => {
    mockAccept.mockReset();
    mockReplace.mockReset();
    mockBack.mockReset();
    __resetPendingInvitationForTests();
  });

  it("states compatibility is not yet available", () => {
    const { getByText } = render(<Consent />);
    expect(getByText("Compatibility analysis is not yet available.")).toBeTruthy();
  });

  it("keeps the connect button disabled until consent is explicitly given", () => {
    const { getByTestId } = render(<Consent />);
    const connect = getByTestId("connect");
    expect(connect.props.accessibilityState.disabled).toBe(true);
    fireEvent.press(connect);
    expect(mockAccept).not.toHaveBeenCalled();
  });

  it("enables and accepts once the toggle is turned on", async () => {
    mockAccept.mockResolvedValueOnce({ couple_id: "c1" });
    const { getByTestId } = render(<Consent />);
    fireEvent.press(getByTestId("consent-toggle"));
    expect(getByTestId("consent-toggle").props.accessibilityState.checked).toBe(true);
    const connect = getByTestId("connect");
    expect(connect.props.accessibilityState.disabled).toBe(false);
    fireEvent.press(connect);
    await waitFor(() => expect(mockAccept).toHaveBeenCalledWith(TOKEN));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/(app)/paired"));
  });

  it("accepts AT MOST ONCE even under rapid double taps", async () => {
    let resolve!: (v: unknown) => void;
    mockAccept.mockImplementationOnce(() => new Promise((r) => (resolve = r)));
    const { getByTestId } = render(<Consent />);
    fireEvent.press(getByTestId("consent-toggle"));
    const connect = getByTestId("connect");
    fireEvent.press(connect);
    fireEvent.press(connect); // concurrent second tap
    fireEvent.press(connect); // and a third
    resolve({ couple_id: "c1" });
    await waitFor(() => expect(mockReplace).toHaveBeenCalled());
    expect(mockAccept).toHaveBeenCalledTimes(1);
  });

  it("shows an invalidated state (not a retry) on a terminal rejection", async () => {
    mockAccept.mockRejectedValueOnce(new ApiError({ kind: "http", status: 409, message: "consumed" }));
    const { getByTestId, queryByTestId } = render(<Consent />);
    fireEvent.press(getByTestId("consent-toggle"));
    fireEvent.press(getByTestId("connect"));
    await waitFor(() => expect(getByTestId("invalidated-home")).toBeTruthy());
    // The connect affordance is gone — no blind retry path for a spent token.
    expect(queryByTestId("connect")).toBeNull();
    expect(mockReplace).not.toHaveBeenCalledWith("/(app)/paired");
  });

  it("keeps a recoverable state (retryable) on an ambiguous transport failure", async () => {
    mockAccept.mockRejectedValueOnce(new ApiError({ kind: "network", message: "offline" }));
    const { getByTestId } = render(<Consent />);
    fireEvent.press(getByTestId("consent-toggle"));
    fireEvent.press(getByTestId("connect"));
    // Still on the consent screen with the connect button available for a
    // deliberate (user-initiated) retry — no auto-retry, no invalidated state.
    await waitFor(() => expect(getByTestId("connect")).toBeTruthy());
    expect(mockReplace).not.toHaveBeenCalled();
    // A second deliberate tap is allowed and succeeds.
    mockAccept.mockResolvedValueOnce({ couple_id: "c1" });
    fireEvent.press(getByTestId("connect"));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/(app)/paired"));
    expect(mockAccept).toHaveBeenCalledTimes(2);
  });
});
