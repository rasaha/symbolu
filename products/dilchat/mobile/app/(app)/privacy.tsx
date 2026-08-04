import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Link } from "expo-router";

import { Body, Card, Heading, Screen, colors } from "@/ui/components";

const POINTS: string[] = [
  "Each person keeps their own private account and birth profile.",
  "Connecting does NOT expose all of your private profile fields to your partner.",
  "Only information you explicitly authorize to share becomes visible to the other person.",
  "Your private content is not automatically copied into a shared context.",
  "Either person can end the connection at any time.",
  "Ending the connection immediately revokes shared access.",
  "Compatibility analysis is not yet available.",
];

/** Static privacy reference page. Mirrors the consent screen's points. */
export default function Privacy(): React.ReactElement {
  return (
    <Screen>
      <Heading>Privacy</Heading>
      <Body muted>How your information is kept private, and what connecting does and does not do.</Body>

      <Card>
        {POINTS.map((p) => (
          <View key={p} style={styles.point}>
            <Text style={styles.bullet}>{"•"}</Text>
            <Body>{p}</Body>
          </View>
        ))}
      </Card>

      <Link href="/(app)/home" accessibilityRole="link" testID="go-home">
        <Body>Back to home.</Body>
      </Link>
    </Screen>
  );
}

const styles = StyleSheet.create({
  point: { flexDirection: "row", gap: 8, alignItems: "flex-start" },
  bullet: { fontSize: 16, lineHeight: 22, color: colors.text },
});
