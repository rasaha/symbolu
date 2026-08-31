import React from "react";
import { Text, View } from "react-native";
import { useRouter } from "expo-router";

import { userMessageFor } from "@/api/errors";
import { useBirthProfile, useCurrentCouple, useMe } from "@/query/hooks";
import { Body, Button, Card, ErrorText, Heading, Loading, Screen } from "@/ui/components";

/**
 * Signed-in home / status screen. Summarizes the account, whether a birth
 * profile exists, and pairing status, and routes to the feature screens.
 * Exposes no compatibility / Guna / astrology value.
 */
export default function Home(): React.ReactElement {
  const router = useRouter();
  const me = useMe();
  const profile = useBirthProfile();
  const couple = useCurrentCouple();

  if (me.isLoading || profile.isLoading || couple.isLoading) {
    return (
      <Screen scroll={false}>
        <Loading label="Loading your account…" />
      </Screen>
    );
  }

  const paired = !!couple.data;
  const hasProfile = !!profile.data;
  const anyError = me.error || profile.error || couple.error;

  return (
    <Screen>
      <Heading>DilChat</Heading>
      <Card>
        <Body>Signed in as</Body>
        <View testID="me-email">
          <Body>{me.data?.email ?? "your account"}</Body>
        </View>
      </Card>

      {anyError ? <ErrorText>{userMessageFor(anyError)}</ErrorText> : null}

      <Card>
        <Body>
          Birth profile:{" "}
          <Text testID="profile-status">{hasProfile ? "saved" : "not created yet"}</Text>
        </Body>
        <Body>
          Partner connection:{" "}
          <Text testID="pairing-status">{paired ? "connected" : "not connected"}</Text>
        </Body>
      </Card>

      <Button
        title={hasProfile ? "View / edit birth profile" : "Create birth profile"}
        testID="go-profile"
        onPress={() => router.push("/(app)/profile")}
      />

      {paired ? (
        <>
          <Button title="Chat" testID="go-chat" onPress={() => router.push("/(app)/chat")} />
          <Button title="Your connection" testID="go-paired" onPress={() => router.push("/(app)/paired")} />
        </>
      ) : (
        <>
          <Button title="Invite a partner" testID="go-invite" onPress={() => router.push("/(app)/invite")} />
          <Button
            title="Accept an invitation"
            variant="secondary"
            testID="go-accept"
            onPress={() => router.push("/(app)/accept")}
          />
        </>
      )}

      <Button
        title="Compatibility"
        variant="secondary"
        testID="go-compatibility"
        onPress={() => router.push("/(app)/compatibility")}
      />
      <Button title="Privacy" variant="secondary" testID="go-privacy" onPress={() => router.push("/(app)/privacy")} />
      <Button title="Settings" variant="secondary" testID="go-settings" onPress={() => router.push("/(app)/settings")} />
    </Screen>
  );
}
