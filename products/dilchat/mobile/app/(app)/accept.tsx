import React, { useState } from "react";
import { useRouter } from "expo-router";

import { parseDeepLink } from "@/deeplink/parse";
import { normalizeInvitationToken } from "@/invitation/token";
import { Body, Button, Heading, Screen, TextField } from "@/ui/components";

/**
 * Accept an invitation by pasting either the invitation code OR the full
 * invitation link. This screen only resolves a clean token and routes to the
 * consent screen — the actual accept call happens only after explicit consent
 * there (consent is never bypassed).
 */
function resolveToken(input: string): string | null {
  const value = input.trim();
  if (!value) return null;
  // If it looks like a link, parse it with the versioned, allowlisted parser so
  // a pasted link (possibly with surrounding text stripped by trim) yields the
  // token unambiguously — never a guess out of arbitrary prose.
  if (/:\/\//.test(value)) {
    const parsed = parseDeepLink(value);
    return parsed.kind === "invitation" ? parsed.token : null;
  }
  return normalizeInvitationToken(value);
}

export default function Accept(): React.ReactElement {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onReview = (): void => {
    setError(null);
    const resolved = resolveToken(token);
    if (!resolved) {
      setError("That code doesn't look right. Paste the exact invitation code or link your partner shared.");
      return;
    }
    router.push({ pathname: "/(app)/consent", params: { token: resolved } });
  };

  return (
    <Screen>
      <Heading>Accept an invitation</Heading>
      <Body muted>
        Enter the invitation code your partner shared with you, or paste the whole invitation link. You will review what
        connecting means and give your consent before anything is connected.
      </Body>

      <TextField
        label="Invitation code or link"
        testID="token"
        value={token}
        onChangeText={setToken}
        autoCapitalize="none"
        autoCorrect={false}
        error={error ?? undefined}
      />

      <Button title="Review & consent" testID="review" onPress={onReview} />
      <Button title="Back" variant="secondary" testID="back" onPress={() => router.back()} />
    </Screen>
  );
}
