import React, { useState } from "react";
import { useRouter } from "expo-router";

import { Body, Button, ErrorText, Heading, Screen, TextField } from "@/ui/components";

/**
 * Accept an invitation. This screen only collects the invitation code and then
 * routes to the consent screen — the actual accept call happens only after
 * explicit consent there.
 */
export default function Accept(): React.ReactElement {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onReview = (): void => {
    setError(null);
    const value = token.trim();
    if (!value) {
      setError("Enter the invitation code you were given.");
      return;
    }
    router.push({ pathname: "/(app)/consent", params: { token: value } });
  };

  return (
    <Screen>
      <Heading>Accept an invitation</Heading>
      <Body muted>
        Enter the invitation code your partner shared with you. You will review what connecting means and give your
        consent before anything is connected.
      </Body>

      <TextField
        label="Invitation code"
        testID="token"
        value={token}
        onChangeText={setToken}
        autoCapitalize="none"
        autoCorrect={false}
      />

      {error ? <ErrorText>{error}</ErrorText> : null}

      <Button title="Review & consent" testID="review" onPress={onReview} />
      <Button title="Back" variant="secondary" testID="back" onPress={() => router.back()} />
    </Screen>
  );
}
