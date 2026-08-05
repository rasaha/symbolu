import React from "react";
import { render } from "@testing-library/react-native";

import Compatibility from "../app/(app)/compatibility";

jest.mock("expo-router", () => {
  const ReactActual = require("react");
  return {
    Link: ({ children }: { children: React.ReactNode }) => ReactActual.createElement(ReactActual.Fragment, null, children),
  };
});

describe("Compatibility screen", () => {
  it("renders the exact 'not yet available' message", () => {
    const { getByTestId, getByText } = render(<Compatibility />);
    expect(getByTestId("compat-unavailable")).toBeTruthy();
    expect(getByText("Compatibility analysis is not yet available.")).toBeTruthy();
  });

  it("shows no number, score, or Guna/Koota value anywhere", () => {
    const { queryByText } = render(<Compatibility />);
    // No visible text node contains a digit (no score/placeholder number).
    expect(queryByText(/[0-9]/)).toBeNull();
    expect(queryByText(/guna/i)).toBeNull();
    expect(queryByText(/koota/i)).toBeNull();
    expect(queryByText(/score/i)).toBeNull();
    expect(queryByText(/compatible/i)).toBeNull();
  });
});
