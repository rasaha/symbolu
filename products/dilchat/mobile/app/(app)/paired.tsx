import React, { useRef, useState } from "react";
import { Text, View } from "react-native";
import { Link, useRouter } from "expo-router";

import { ApiError, userMessageFor } from "@/api/errors";
import { useCurrentCouple, useUnpair } from "@/query/hooks";
import { Body, Button, Card, ErrorText, Heading, Loading, Screen } from "@/ui/components";

/**
 * Paired status. Shows only minimal relationship metadata — couple status and
 * the members' scope slots. It never shows a partner's private profile fields
 * (the couple payload contains none), and exposes no compatibility value.
 */
export default function Paired(): React.ReactElement {
  const router = useRouter();
  const couple = useCurrentCouple();
  const unpair = useUnpair();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Guards against a second unpair mutation from a rapid/double confirm tap.
  const inFlight = useRef(false);

  if (couple.isLoading) {
    return (
      <Screen scroll={false}>
        <Loading label="Loading your connection…" />
      </Screen>
    );
  }

  if (couple.error) {
    return (
      <Screen>
        <Heading>Your connection</Heading>
        <ErrorText>{userMessageFor(couple.error)}</ErrorText>
        <Link href="/(app)/home" accessibilityRole="link" testID="go-home">
          <Body>Back to home.</Body>
        </Link>
      </Screen>
    );
  }

  const data = couple.data;
  if (!data) {
    return (
      <Screen>
        <Heading>No connection yet</Heading>
        <Body muted>You are not connected with a partner.</Body>
        <Link href="/(app)/home" accessibilityRole="link" testID="go-home">
          <Body>Back to home.</Body>
        </Link>
      </Screen>
    );
  }

  const onUnpair = async (): Promise<void> => {
    setError(null);
    if (inFlight.current) return; // no duplicate / concurrent unpair
    inFlight.current = true;
    try {
      await unpair.mutateAsync(data.couple_id);
      router.replace("/(app)/home");
    } catch (e) {
      // If the couple is already gone (e.g. the server committed the unpair but
      // the response was lost, or the partner unpaired first), that IS the
      // intended end state — treat 404/409 as done rather than blind-retrying.
      if (e instanceof ApiError && e.kind === "http" && (e.status === 404 || e.status === 409)) {
        await couple.refetch();
        router.replace("/(app)/home");
      } else {
        // Ambiguous transport failure: do NOT auto-retry a destructive action.
        // Show a neutral recovery state and let the user refresh authoritative
        // server state or retry deliberately.
        setError(userMessageFor(e));
      }
    } finally {
      inFlight.current = false;
    }
  };

  const onRefresh = async (): Promise<void> => {
    setError(null);
    await couple.refetch();
  };

  return (
    <Screen>
      <Heading>Your connection</Heading>

      <Card>
        <Body>
          Status: <Text testID="couple-status">{data.status}</Text>
        </Body>
        <Body>Members</Body>
        {data.members.map((m) => (
          <View key={m.user_id} testID={`member-slot-${m.scope_slot}`}>
            <Body muted>
              {m.scope_slot} — {m.status}
            </Body>
          </View>
        ))}
      </Card>

      <Body muted>
        Ending the connection immediately revokes any shared access between the two accounts.
      </Body>

      {error ? (
        <>
          <ErrorText>{error}</ErrorText>
          <Button
            title="Check current status"
            variant="secondary"
            testID="refresh-status"
            onPress={onRefresh}
            loading={couple.isRefetching}
          />
        </>
      ) : null}

      {confirming ? (
        <Card>
          <Body>End this connection? This cannot be undone and revokes shared access immediately.</Body>
          <Button
            title="Yes, end connection"
            variant="danger"
            testID="confirm-unpair"
            onPress={onUnpair}
            loading={unpair.isPending}
          />
          <Button
            title="Keep connection"
            variant="secondary"
            testID="cancel-unpair"
            onPress={() => setConfirming(false)}
          />
        </Card>
      ) : (
        <Button
          title="End connection (unpair)"
          variant="danger"
          testID="unpair"
          onPress={() => setConfirming(true)}
        />
      )}
    </Screen>
  );
}
