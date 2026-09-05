import React from "react";
import { AppState, type AppStateStatus, Text } from "react-native";
import { act, render, within } from "@testing-library/react-native";

import { AppSwitcherShield } from "@/privacy/AppSwitcherShield";

// Drive AppState transitions through a captured listener.
let listener: ((s: AppStateStatus) => void) | null = null;

beforeEach(() => {
  listener = null;
  jest.spyOn(AppState, "addEventListener").mockImplementation(((_evt: string, cb: (s: AppStateStatus) => void) => {
    listener = cb;
    return { remove: jest.fn() };
  }) as unknown as typeof AppState.addEventListener);
  // Start active.
  Object.defineProperty(AppState, "currentState", { value: "active", configurable: true });
});

afterEach(() => jest.restoreAllMocks());

describe("AppSwitcherShield — background privacy cover", () => {
  it("does not cover content while active", () => {
    const { queryByTestId, getByText } = render(
      <AppSwitcherShield>
        <Text>secret birth data</Text>
      </AppSwitcherShield>,
    );
    expect(getByText("secret birth data")).toBeTruthy();
    expect(queryByTestId("app-switcher-shield", { includeHiddenElements: true })).toBeNull();
  });

  it("covers content when the app becomes inactive (app-switcher snapshot)", () => {
    const { queryByTestId } = render(
      <AppSwitcherShield>
        <Text>secret birth data</Text>
      </AppSwitcherShield>,
    );
    act(() => listener?.("inactive"));
    expect(queryByTestId("app-switcher-shield", { includeHiddenElements: true })).toBeTruthy();
  });

  it("covers on background and removes the cover on resume (no permanent blank)", () => {
    const { queryByTestId } = render(
      <AppSwitcherShield>
        <Text>secret birth data</Text>
      </AppSwitcherShield>,
    );
    act(() => listener?.("background"));
    expect(queryByTestId("app-switcher-shield", { includeHiddenElements: true })).toBeTruthy();
    act(() => listener?.("active"));
    expect(queryByTestId("app-switcher-shield", { includeHiddenElements: true })).toBeNull();
  });

  it("the cover exposes no user data and is hidden from the accessibility tree", () => {
    const { getByTestId } = render(
      <AppSwitcherShield>
        <Text>secret birth data</Text>
      </AppSwitcherShield>,
    );
    act(() => listener?.("inactive"));
    const cover = getByTestId("app-switcher-shield", { includeHiddenElements: true });
    expect(cover.props.accessibilityElementsHidden).toBe(true);
    // Only neutral copy in the cover — no birth data, token, email, or pairing info.
    const scoped = within(cover);
    expect(scoped.getByText("DilChat", { includeHiddenElements: true })).toBeTruthy();
    expect(scoped.queryByText("secret birth data", { includeHiddenElements: true })).toBeNull();
  });
});
