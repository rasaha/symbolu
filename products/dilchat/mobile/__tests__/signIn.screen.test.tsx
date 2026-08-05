import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import SignIn from "../app/(auth)/sign-in";

const mockSignIn = jest.fn();

jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({ signIn: mockSignIn }),
}));

jest.mock("expo-router", () => {
  const ReactActual = require("react");
  return {
    Link: ({ children }: { children: React.ReactNode }) => ReactActual.createElement(ReactActual.Fragment, null, children),
  };
});

describe("SignIn screen", () => {
  beforeEach(() => mockSignIn.mockReset());

  it("renders the sign-in form", () => {
    const { getByTestId } = render(<SignIn />);
    expect(getByTestId("email")).toBeTruthy();
    expect(getByTestId("password")).toBeTruthy();
    expect(getByTestId("submit")).toBeTruthy();
  });

  it("shows an error and does not sign in on empty submit", () => {
    const { getByTestId, getByText } = render(<SignIn />);
    fireEvent.press(getByTestId("submit"));
    expect(getByText("Enter your email and password.")).toBeTruthy();
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("calls signIn with trimmed email on valid input", async () => {
    mockSignIn.mockResolvedValueOnce(undefined);
    const { getByTestId } = render(<SignIn />);
    fireEvent.changeText(getByTestId("email"), "  a@example.com ");
    fireEvent.changeText(getByTestId("password"), "password123");
    fireEvent.press(getByTestId("submit"));
    await waitFor(() => expect(mockSignIn).toHaveBeenCalledWith("a@example.com", "password123"));
  });
});
