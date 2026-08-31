import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import Paired from "../app/(app)/paired";
import { ApiError } from "@/api/errors";

const mockUnpair = jest.fn();
const mockReplace = jest.fn();
const mockRefetch = jest.fn().mockResolvedValue(undefined);
let mockCouple: { data: unknown; isLoading: boolean; error: unknown; refetch: jest.Mock; isRefetching: boolean };

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
    mockRefetch.mockClear();
    mockCouple = { data: COUPLE, isLoading: false, error: null, refetch: mockRefetch, isRefetching: false };
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
    mockCouple = { data: null, isLoading: false, error: null, refetch: mockRefetch, isRefetching: false };
    const { getByText, queryByTestId } = render(<Paired />);
    expect(getByText("No connection yet")).toBeTruthy();
    expect(queryByTestId("unpair")).toBeNull();
  });

  it("does NOT blind-retry on an ambiguous unpair failure; offers a status refresh", async () => {
    mockUnpair.mockRejectedValueOnce(new ApiError({ kind: "network", message: "offline" }));
    const { getByTestId } = render(<Paired />);
    fireEvent.press(getByTestId("unpair"));
    fireEvent.press(getByTestId("confirm-unpair"));
    await waitFor(() => expect(getByTestId("refresh-status")).toBeTruthy());
    // Exactly one attempt — no automatic retry of a destructive action.
    expect(mockUnpair).toHaveBeenCalledTimes(1);
    expect(mockReplace).not.toHaveBeenCalled();
    // The user can deliberately refresh authoritative server state.
    fireEvent.press(getByTestId("refresh-status"));
    await waitFor(() => expect(mockRefetch).toHaveBeenCalled());
  });

  it("treats an already-unpaired (404) response as done, not an error", async () => {
    mockUnpair.mockRejectedValueOnce(new ApiError({ kind: "http", status: 404, message: "gone" }));
    const { getByTestId } = render(<Paired />);
    fireEvent.press(getByTestId("unpair"));
    fireEvent.press(getByTestId("confirm-unpair"));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/(app)/home"));
    expect(mockRefetch).toHaveBeenCalled();
  });
});
