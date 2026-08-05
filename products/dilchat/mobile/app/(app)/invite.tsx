import React, { useState } from "react";
import { Share, StyleSheet, Text, View } from "react-native";
import { Link, useRouter } from "expo-router";

import { userMessageFor } from "@/api/errors";
import type { InvitationCreateResponse } from "@/api/types";
import { buildInvitationLink } from "@/deeplink/parse";
import { useCreateInvitation, useCurrentCouple } from "@/query/hooks";
import { Body, Button, Card, ErrorText, Heading, Loading, Screen, colors } from "@/ui/components";

/**
 * Create a partner invitation. The token is shown for the user to share and a
 * shareable deep link is generated; neither is ever written to logs. Neutral
 * wording only — no relationship framing.
 */
export default function Invite(): React.ReactElement {
  const router = useRouter();
  const couple = useCurrentCouple();
  const create = useCreateInvitation();
  const [invitation, setInvitation] = useState<InvitationCreateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (couple.isLoading) {
    return (
      <Screen scroll={false}>
        <Loading label="Checking your connection status…" />
      </Screen>
    );
  }

  if (couple.data) {
    return (
      <Screen>
        <Heading>Already connected</Heading>
        <Body>You are already connected with a partner, so a new invitation is not needed.</Body>
        <Link href="/(app)/paired" accessibilityRole="link" testID="go-paired">
          <Body>View your connection.</Body>
        </Link>
      </Screen>
    );
  }

  const onCreate = async (): Promise<void> => {
    setError(null);
    try {
      // Do not log the token; only place it into local component state for display.
      const result = await create.mutateAsync();
      setInvitation(result);
    } catch (e) {
      setError(userMessageFor(e));
    }
  };

  const onShare = async (link: string): Promise<void> => {
    try {
      // The OS share sheet is user-initiated; we never auto-post or log the link.
      await Share.share({ message: link });
    } catch {
      // A dismissed/failed share sheet is a no-op; the code remains on screen.
    }
  };

  return (
    <Screen>
      <Heading>Invite a partner</Heading>
      <Body muted>
        Create an invitation and share the code or link with the person you want to connect with. They enter it in their
        own account to connect.
      </Body>

      {error ? <ErrorText>{error}</ErrorText> : null}

      {invitation ? (
        <Card>
          <Body>Invitation code</Body>
          <Text testID="invitation-token" selectable style={styles.token}>
            {invitation.token}
          </Text>
          <View testID="invitation-expiry">
            <Body muted>Expires: {invitation.expires_at}</Body>
          </View>
          <Button
            title="Share invitation link"
            testID="share-invitation"
            onPress={() => onShare(buildInvitationLink(invitation.token))}
          />
          <Body muted>
            Share this with your partner through a channel you trust. Anyone with the code or link can use it to connect,
            so share it only with that person.
          </Body>
        </Card>
      ) : (
        <Button title="Create invitation" testID="create-invitation" onPress={onCreate} loading={create.isPending} />
      )}

      <Link href="/(app)/privacy" accessibilityRole="link" testID="go-privacy">
        <Body>How connecting affects your privacy.</Body>
      </Link>
      <Button title="Back" variant="secondary" testID="back" onPress={() => router.back()} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  token: { fontSize: 18, fontWeight: "700", color: colors.text, letterSpacing: 1 },
});
