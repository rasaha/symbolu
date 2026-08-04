import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import Consent from "../app/(app)/consent";

const mockAccept = jest.fn();
const mockReplace = jest.fn();
const mockBack = jest.fn();

jest.mock("@/query/hooks", () => ({
  useAcceptInvitation: () => ({ mutateAsync: mockAccept, isPending: false }),
}));

jest.mock("expo-router", () => ({
  useRouter: () => ({ replace: mockReplace, back: mockBack, push: jest.fn() }),
  useLocalSearchParams: () => ({ token: "TOKEN123" }),
}));

describe("Consent screen", () => {
  beforeEach(() => {
    mockAccept.mockReset();
    mockReplace.mockReset();
  });

  it("states compatibility is not yet available", () => {
    const { getByText } = render(<Consent />);
    expect(getByText("Compatibility analysis is not yet available.")).toBeTruthy();
  });

  it("keeps the connect button disabled until consent is explicitly given", () => {
    const { getByTestId } = render(<Consent />);
    const connect = getByTestId("connect");
    expect(connect.props.accessibilityState.disabled).toBe(true);
    // Pressing while disabled must not accept.
    fireEvent.press(connect);
    expect(mockAccept).not.toHaveBeenCalled();
  });

  it("enables and accepts once the toggle is turned on", async () => {
    mockAccept.mockResolvedValueOnce({ couple_id: "c1" });
    const { getByTestId } = render(<Consent />);
    const toggle = getByTestId("consent-toggle");
    expect(toggle.props.accessibilityState.checked).toBe(false);
    fireEvent.press(toggle);
    expect(getByTestId("consent-toggle").props.accessibilityState.checked).toBe(true);
    const connect = getByTestId("connect");
    expect(connect.props.accessibilityState.disabled).toBe(false);
    fireEvent.press(connect);
    await waitFor(() => expect(mockAccept).toHaveBeenCalledWith("TOKEN123"));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/(app)/paired"));
  });
});
