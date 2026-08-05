import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import Paired from "../app/(app)/paired";

const mockUnpair = jest.fn();
const mockReplace = jest.fn();
let mockCouple: { data: unknown; isLoading: boolean; error: unknown };

jest.mock("@/query/hooks", () => ({
  useCurrentCouple: () => mockCouple,
  useUnpair: () => ({ mutateAsync: mockUnpair, isPending: false }),
}));

jest.mock("expo-router", () => {
  const ReactActual = require("react");
  return {
    useRouter: () => ({ replace: mockReplace, push: jest.fn(), back: jest.fn() }),
    Link: ({ children }: { children: React.ReactNode }) => ReactActual.createElement(ReactActual.Fragment, null, children),
  };
});

const COUPLE = {
  couple_id: "c1",
  status: "ACTIVE",
  members: [
    { user_id: "u1", scope_slot: "PRIVATE_A", status: "ACTIVE" },
    { user_id: "u2", scope_slot: "PRIVATE_B", status: "ACTIVE" },
  ],
};

describe("Paired screen", () => {
  beforeEach(() => {
    mockUnpair.mockReset();
    mockReplace.mockReset();
    mockCouple = { data: COUPLE, isLoading: false, error: null };
  });

  it("shows only couple status and scope slots (no partner private fields)", () => {
    const { getByTestId, getByText, queryByText } = render(<Paired />);
    expect(getByTestId("couple-status")).toBeTruthy();
    expect(getByText("ACTIVE")).toBeTruthy();
    expect(getByTestId("member-slot-PRIVATE_A")).toBeTruthy();
    expect(getByTestId("member-slot-PRIVATE_B")).toBeTruthy();
    // No partner private profile fields are rendered — the couple payload has none.
    expect(queryByText(/birth_date/i)).toBeNull();
    expect(queryByText(/preferred_name/i)).toBeNull();
    expect(queryByText(/1990/)).toBeNull();
  });

  it("requires a confirm step, then calls unpair with the couple id", async () => {
    mockUnpair.mockResolvedValueOnce(undefined);
    const { getByTestId, queryByTestId } = render(<Paired />);
    // Confirm control is not shown until the user asks to unpair.
    expect(queryByTestId("confirm-unpair")).toBeNull();
    fireEvent.press(getByTestId("unpair"));
    fireEvent.press(getByTestId("confirm-unpair"));
    await waitFor(() => expect(mockUnpair).toHaveBeenCalledWith("c1"));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/(app)/home"));
  });

  it("shows an empty state when not paired", () => {
    mockCouple = { data: null, isLoading: false, error: null };
    const { getByText, queryByTestId } = render(<Paired />);
    expect(getByText("No connection yet")).toBeTruthy();
    expect(queryByTestId("unpair")).toBeNull();
  });
});
