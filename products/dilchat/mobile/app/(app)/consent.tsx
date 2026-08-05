import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { userMessageFor } from "@/api/errors";
import { useAcceptInvitation } from "@/query/hooks";
import { Body, Button, Card, ErrorText, Heading, Screen, colors } from "@/ui/components";

const POINTS: string[] = [
  "Each person keeps their own private account and birth profile.",
  "Connecting does NOT expose all of your private profile fields to your partner.",
  "Only information you explicitly authorize to share becomes visible to the other person.",
  "Your private content is not automatically copied into a shared context.",
  "Either person can end the connection at any time.",
  "Ending the connection immediately revokes shared access.",
  "Compatibility analysis is not yet available.",
];

/**
 * Pairing consent. Consent is explicit and unchecked by default; the connect
 * action runs the accept mutation only after the toggle is turned on.
 */
export default function Consent(): React.ReactElement {
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string }>();
  const token = typeof params.token === "string" ? params.token : "";
  const accept = useAcceptInvitation();
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onConnect = async (): Promise<void> => {
    setError(null);
    if (!agreed || !token) return;
    try {
      await accept.mutateAsync(token);
      router.replace("/(app)/paired");
    } catch (e) {
      setError(userMessageFor(e));
    }
  };

  return (
    <Screen>
      <Heading>Before you connect</Heading>
      <Body muted>Please read how connecting works, then decide.</Body>

      <Card>
        {POINTS.map((p) => (
          <View key={p} style={styles.point}>
            <Text style={styles.bullet}>{"•"}</Text>
            <Body>{p}</Body>
          </View>
        ))}
      </Card>

      {!token ? <ErrorText>This invitation link is missing its code. Go back and enter it again.</ErrorText> : null}

      <Pressable
        testID="consent-toggle"
        accessibilityRole="checkbox"
        accessibilityState={{ checked: agreed }}
        accessibilityLabel="I understand and consent to connecting"
        onPress={() => setAgreed((v) => !v)}
        style={styles.toggleRow}
      >
        <View style={[styles.box, agreed && styles.boxChecked]}>
          {agreed ? <Text style={styles.check}>{"✓"}</Text> : null}
        </View>
        <Body>I understand the above and consent to connecting.</Body>
      </Pressable>

      {error ? <ErrorText>{error}</ErrorText> : null}

      <Button
        title="I consent — connect"
        testID="connect"
        onPress={onConnect}
        disabled={!agreed || !token}
        loading={accept.isPending}
      />
      <Button title="Cancel" variant="secondary" testID="cancel" onPress={() => router.back()} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  point: { flexDirection: "row", gap: 8, alignItems: "flex-start" },
  bullet: { fontSize: 16, lineHeight: 22, color: colors.text },
  toggleRow: { flexDirection: "row", gap: 12, alignItems: "center", minHeight: 48 },
  box: {
    width: 28,
    height: 28,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  boxChecked: { backgroundColor: colors.primary, borderColor: colors.primary },
  check: { color: colors.primaryText, fontSize: 18, fontWeight: "700" },
});
