import React, { useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { ApiError, userMessageFor } from "@/api/errors";
import { useAcceptInvitation } from "@/query/hooks";
import { clearPendingInvitation, usePendingInvitation } from "@/invitation/pendingInvitation";
import { normalizeInvitationToken } from "@/invitation/token";
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
 * An invitation acceptance that can never succeed with this token — the backend
 * has definitively rejected it (invalid, expired, consumed, self-issued, or the
 * user is already paired). Distinct from a transport failure, which is
 * recoverable and must NOT be blind-retried.
 */
function isTerminalInvitationError(e: unknown): boolean {
  return (
    e instanceof ApiError &&
    e.kind === "http" &&
    e.status !== null &&
    [400, 404, 409, 410, 422].includes(e.status)
  );
}

/**
 * Pairing consent. Consent is explicit and unchecked by default; the accept
 * mutation runs only after the toggle is on, runs AT MOST ONCE, and is never
 * blind-retried on an ambiguous (network/timeout) failure.
 */
export default function Consent(): React.ReactElement {
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string }>();
  const pending = usePendingInvitation();
  // Token comes from the route param (manual entry or deep-link nav) and falls
  // back to the in-memory pending invitation (deep-link resume). Normalized so a
  // stray link/whitespace never reaches the backend as a token.
  const token =
    normalizeInvitationToken(typeof params.token === "string" ? params.token : undefined) ??
    pending?.token ??
    null;

  const accept = useAcceptInvitation();
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // "idle" → user may connect; "done" → already accepted, block re-accept;
  // "invalidated" → token can never work, offer a way out.
  const [phase, setPhase] = useState<"idle" | "done" | "invalidated">("idle");
  // Hard guard against concurrent / double taps landing two accept mutations.
  const inFlight = useRef(false);

  const onConnect = async (): Promise<void> => {
    setError(null);
    if (!agreed || !token) return;
    if (phase !== "idle") return;
    if (inFlight.current) return; // repeated / concurrent tap
    inFlight.current = true;
    try {
      await accept.mutateAsync(token);
      // Success is authoritative: consume the pending context exactly once.
      clearPendingInvitation();
      setPhase("done");
      router.replace("/(app)/paired");
    } catch (e) {
      if (isTerminalInvitationError(e)) {
        // The token is spent/invalid — drop it so it cannot restore a relationship
        // or be retried, and route the user forward rather than trapping them.
        clearPendingInvitation();
        setPhase("invalidated");
        setError(userMessageFor(e));
      } else {
        // Ambiguous transport failure: keep the pending context, show a neutral
        // recovery state, and let the user retry deliberately. No auto-retry.
        setError(userMessageFor(e));
      }
    } finally {
      inFlight.current = false;
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

      {!token ? (
        <ErrorText>This invitation link is missing its code. Go back and enter it again.</ErrorText>
      ) : null}

      {phase === "invalidated" ? (
        <Card>
          <Body>
            This invitation can no longer be used. Ask your partner to send a new one, or return to your home screen.
          </Body>
          <Button title="Back to home" testID="invalidated-home" onPress={() => router.replace("/(app)/home")} />
        </Card>
      ) : (
        <>
          <Pressable
            testID="consent-toggle"
            accessibilityRole="checkbox"
            accessibilityState={{ checked: agreed, disabled: phase !== "idle" }}
            accessibilityLabel="I understand and consent to connecting"
            accessibilityHint="Double tap to toggle your consent before connecting"
            disabled={phase !== "idle"}
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
            disabled={!agreed || !token || phase !== "idle"}
            loading={accept.isPending}
          />
          <Button
            title="Cancel"
            variant="secondary"
            testID="cancel"
            onPress={() => {
              // Explicit rejection clears the pending invitation context.
              clearPendingInvitation();
              router.back();
            }}
          />
        </>
      )}
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
