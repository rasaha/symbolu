import React, { useState } from "react";
import { View } from "react-native";
import { useRouter } from "expo-router";

import { userMessageFor } from "@/api/errors";
import { useAuth } from "@/auth/AuthContext";
import { useMe } from "@/query/hooks";
import { Body, Button, Card, ErrorText, Heading, Screen } from "@/ui/components";

/**
 * Settings / sign-out. Signing out clears all locally cached account data so no
 * data leaks across account switches.
 */
export default function Settings(): React.ReactElement {
  const router = useRouter();
  const { signOut } = useAuth();
  const me = useMe();
  const [busy, setBusy] = useState<"device" | "all" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const doSignOut = async (scope: "device" | "all"): Promise<void> => {
    setError(null);
    setBusy(scope);
    try {
      await signOut(scope);
      router.replace("/(auth)/sign-in");
    } catch (e) {
      setError(userMessageFor(e));
      setBusy(null);
    }
  };

  return (
    <Screen>
      <Heading>Settings</Heading>

      <Card>
        <Body>Signed in as</Body>
        <View testID="me-email">
          <Body>{me.data?.email ?? "your account"}</Body>
        </View>
      </Card>

      <Body muted>
        Signing out clears this device's cached account data. Switching accounts always starts from a clean state.
      </Body>

      {error ? <ErrorText>{error}</ErrorText> : null}

      <Button
        title="Sign out"
        testID="sign-out"
        onPress={() => doSignOut("device")}
        loading={busy === "device"}
        disabled={busy === "all"}
      />
      <Button
        title="Sign out of all devices"
        variant="secondary"
        testID="sign-out-all"
        onPress={() => doSignOut("all")}
        loading={busy === "all"}
        disabled={busy === "device"}
      />
    </Screen>
  );
}
