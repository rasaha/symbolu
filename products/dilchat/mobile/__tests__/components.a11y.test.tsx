import React from "react";
import { render } from "@testing-library/react-native";

import { Button, ErrorText, Heading, Loading, TextField } from "@/ui/components";

describe("shared UI accessibility", () => {
  it("Heading exposes the header role", () => {
    const { getByRole } = render(<Heading>Sign in</Heading>);
    expect(getByRole("header")).toBeTruthy();
  });

  it("Button exposes role, label, and disabled/busy state", () => {
    const { getByTestId, rerender } = render(
      <Button title="Connect" testID="b" onPress={() => undefined} />,
    );
    const btn = getByTestId("b");
    expect(btn.props.accessibilityRole).toBe("button");
    expect(btn.props.accessibilityLabel).toBe("Connect");
    expect(btn.props.accessibilityState.disabled).toBe(false);

    rerender(<Button title="Connect" testID="b" onPress={() => undefined} loading />);
    const busy = getByTestId("b");
    expect(busy.props.accessibilityState.busy).toBe(true);
    expect(busy.props.accessibilityState.disabled).toBe(true);
  });

  it("TextField associates a label with the input", () => {
    const { getByTestId } = render(
      <TextField label="Email" testID="email" value="" onChangeText={() => undefined} />,
    );
    const input = getByTestId("email");
    expect(input.props.accessibilityLabel).toBe("Email");
  });

  it("ErrorText announces assertively with the alert role (color is not the only signal)", () => {
    const { getByRole, getByText } = render(<ErrorText>Something went wrong</ErrorText>);
    const alert = getByRole("alert");
    expect(alert.props.accessibilityLiveRegion).toBe("assertive");
    // The message text itself conveys the error — not color alone.
    expect(getByText("Something went wrong")).toBeTruthy();
  });

  it("Loading exposes a progressbar with an accessible label", () => {
    const { getByRole } = render(<Loading label="Loading your session…" />);
    const bar = getByRole("progressbar");
    expect(bar.props.accessibilityLabel).toBe("Loading your session…");
  });

  it("Loading has a default label even without an explicit one", () => {
    const { getByRole } = render(<Loading />);
    expect(getByRole("progressbar").props.accessibilityLabel).toBe("Loading");
  });
});
