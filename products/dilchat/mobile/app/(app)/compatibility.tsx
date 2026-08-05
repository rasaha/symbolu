import React from "react";
import { View } from "react-native";
import { Link } from "expo-router";

import { Body, Heading, Screen } from "@/ui/components";

/**
 * Compatibility placeholder. Phase 1 intentionally exposes NO compatibility,
 * Guna, or Koota value of any kind. This screen states only that the feature is
 * unavailable — it must never imply a score was computed.
 */
export default function Compatibility(): React.ReactElement {
  return (
    <Screen>
      <Heading>Compatibility</Heading>
      <View testID="compat-unavailable">
        <Body>Compatibility analysis is not yet available.</Body>
      </View>
      <Body muted>This feature is not part of this version of the app.</Body>
      <Link href="/(app)/home" accessibilityRole="link" testID="go-home">
        <Body>Back to home.</Body>
      </Link>
    </Screen>
  );
}
