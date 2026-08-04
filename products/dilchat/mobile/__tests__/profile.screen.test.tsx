import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import Profile from "../app/(app)/profile";

const mockMutateAsync = jest.fn();
let mockProfileData: unknown = null;

jest.mock("@/query/hooks", () => ({
  useBirthProfile: () => ({ data: mockProfileData, isLoading: false }),
  useSaveBirthProfile: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}));

const mockBack = jest.fn();
jest.mock("expo-router", () => ({
  useRouter: () => ({ back: mockBack, push: jest.fn(), replace: jest.fn() }),
}));

function fillValid(getByTestId: (id: string) => unknown): void {
  const set = (id: string, v: string) => fireEvent.changeText(getByTestId(id) as never, v);
  set("preferred_name", "Asha");
  set("birth_date", "1990-05-14");
  set("birth_time_local", "08:30");
  set("birthplace_label", "Pune");
  set("iana_timezone", "Asia/Kolkata");
  set("latitude", "18.52");
  set("longitude", "73.85");
}

describe("Profile screen", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset();
    mockProfileData = null;
  });

  it("shows validation errors and does not save on bad input", () => {
    const { getByTestId, getByText } = render(<Profile />);
    fireEvent.changeText(getByTestId("birth_date"), "not-a-date");
    fireEvent.press(getByTestId("save"));
    expect(getByText("Enter a name to display.")).toBeTruthy();
    expect(getByText("Use the format YYYY-MM-DD.")).toBeTruthy();
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("calls the save mutation with exists=false when creating", async () => {
    mockMutateAsync.mockResolvedValueOnce({});
    const { getByTestId } = render(<Profile />);
    fillValid((id) => getByTestId(id));
    fireEvent.press(getByTestId("save"));
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    const arg = mockMutateAsync.mock.calls[0][0] as { exists: boolean; body: { preferred_name: string } };
    expect(arg.exists).toBe(false);
    expect(arg.body.preferred_name).toBe("Asha");
    expect(mockBack).toHaveBeenCalled();
  });

  it("passes exists=true when a profile already exists", async () => {
    mockProfileData = {
      id: "bp1",
      version: 1,
      preferred_name: "Asha",
      birth_date: "1990-05-14",
      birth_time_precision: "EXACT",
      has_birth_time: true,
      uncertainty_minutes: null,
      birthplace_label: "Pune",
      iana_timezone: "Asia/Kolkata",
      input_confidence: 1,
      utc_birth_instant: null,
      utc_interval: null,
    };
    mockMutateAsync.mockResolvedValueOnce({});
    const { getByTestId } = render(<Profile />);
    // Latitude/longitude/time are not returned by the API, so re-enter them.
    fireEvent.changeText(getByTestId("birth_time_local"), "08:30");
    fireEvent.changeText(getByTestId("latitude"), "18.52");
    fireEvent.changeText(getByTestId("longitude"), "73.85");
    fireEvent.press(getByTestId("save"));
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    expect((mockMutateAsync.mock.calls[0][0] as { exists: boolean }).exists).toBe(true);
  });
});
