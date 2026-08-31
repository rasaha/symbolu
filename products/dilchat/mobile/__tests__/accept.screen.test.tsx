import React from "react";
import { fireEvent, render } from "@testing-library/react-native";

import Accept from "../app/(app)/accept";
import { APP_SCHEME } from "@/deeplink/parse";

const TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-ab";
const mockPush = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush, back: jest.fn() }),
}));

describe("Accept screen — token/link resolution", () => {
  beforeEach(() => mockPush.mockReset());

  it("routes a pasted bare code to consent (never accepting directly)", () => {
    const { getByTestId } = render(<Accept />);
    fireEvent.changeText(getByTestId("token"), TOKEN);
    fireEvent.press(getByTestId("review"));
    expect(mockPush).toHaveBeenCalledWith({ pathname: "/(app)/consent", params: { token: TOKEN } });
  });

  it("extracts the token from a pasted full invitation link", () => {
    const { getByTestId } = render(<Accept />);
    fireEvent.changeText(getByTestId("token"), `${APP_SCHEME}://invitation?v=1&token=${TOKEN}`);
    fireEvent.press(getByTestId("review"));
    expect(mockPush).toHaveBeenCalledWith({ pathname: "/(app)/consent", params: { token: TOKEN } });
  });

  it("shows an error and does not navigate for junk input", () => {
    const { getByTestId, getByText } = render(<Accept />);
    fireEvent.changeText(getByTestId("token"), "not a real code");
    fireEvent.press(getByTestId("review"));
    expect(mockPush).not.toHaveBeenCalled();
    expect(getByText(/doesn't look right/i)).toBeTruthy();
  });

  it("rejects a link to a non-invitation route", () => {
    const { getByTestId } = render(<Accept />);
    fireEvent.changeText(getByTestId("token"), `${APP_SCHEME}://settings?v=1&token=${TOKEN}`);
    fireEvent.press(getByTestId("review"));
    expect(mockPush).not.toHaveBeenCalled();
  });
});
