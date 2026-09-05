import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlatList, KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from "react-native";
import { Link } from "expo-router";

import { userMessageFor } from "@/api/errors";
import type { MessageResponse } from "@/api/types";
import { newClientMessageId } from "@/chat/clientMessageId";
import { latestSequence, mergeMessages, type ChatListItem, type PendingMessage } from "@/chat/merge";
import { useCurrentConversation, useMe, useMessages, useSendMessage, useUpdateReadState } from "@/query/hooks";
import { Body, Button, colors, ErrorText, Heading, Loading, Screen } from "@/ui/components";

/**
 * Minimal 1:1 text chat over the merged Phase 3A REST backend (Phase 3D).
 *
 * - History pages forward (ascending server_sequence) with server-minted
 *   cursors and is polled via react-query — no WebSocket, no push.
 * - Sends are optimistic and keyed by a client_message_id; a retry after a
 *   timeout reuses the SAME id so the backend's idempotent replay can never
 *   duplicate the message.
 * - Read state is forward-only and mirrors what has actually been loaded.
 * - Tombstoned messages keep their row and render a neutral placeholder.
 */
export default function Chat(): React.ReactElement {
  const me = useMe();
  const conversation = useCurrentConversation();
  const conversationId = conversation.data?.conversation_id;
  const messages = useMessages(conversationId);
  const send = useSendMessage(conversationId);
  const readState = useUpdateReadState(conversationId);

  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<PendingMessage[]>([]);
  const [sendError, setSendError] = useState<string | null>(null);

  const server = useMemo(
    () => (messages.data?.pages ?? []).flatMap((p) => p.messages),
    [messages.data],
  );
  const items = useMemo(() => mergeMessages(server, pending), [server, pending]);

  // Load the full history: the backend pages oldest→newest, so keep following
  // next_cursor until the tail is reached (page size 50; pilot-scale volumes).
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = messages;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Drop pending entries once the server echoes them back (same client id).
  useEffect(() => {
    const confirmed = new Set(server.map((m) => m.client_message_id));
    setPending((prev) =>
      prev.some((p) => confirmed.has(p.client_message_id))
        ? prev.filter((p) => !confirmed.has(p.client_message_id))
        : prev,
    );
  }, [server]);

  // Forward-only read state, pushed at most once per newly seen sequence. Only
  // sequences actually loaded on screen are marked read. A failed update is not
  // retried in a loop — it self-heals when a newer message advances the value.
  const lastPushedRead = useRef(0);
  const conversationLastRead = conversation.data?.last_read_sequence ?? 0;
  useEffect(() => {
    if (lastPushedRead.current < conversationLastRead) lastPushedRead.current = conversationLastRead;
  }, [conversationLastRead]);
  const readMutate = readState.mutate;
  useEffect(() => {
    if (!conversationId || hasNextPage) return; // wait for the loaded tail
    const latest = latestSequence(server);
    if (latest > lastPushedRead.current) {
      lastPushedRead.current = latest;
      readMutate(latest);
    }
  }, [conversationId, hasNextPage, server, readMutate]);

  const markFailed = useCallback((id: string, message: string): void => {
    setPending((prev) => prev.map((p) => (p.client_message_id === id ? { ...p, status: "failed" } : p)));
    setSendError(message);
  }, []);

  const sendMutate = send.mutate;
  const dispatch = useCallback(
    (id: string, body: string): void => {
      sendMutate(
        { client_message_id: id, body },
        { onError: (e) => markFailed(id, userMessageFor(e)) },
      );
    },
    [sendMutate, markFailed],
  );

  const onSend = (): void => {
    const body = draft.trim();
    if (!body || !conversationId) return;
    const id = newClientMessageId();
    setDraft("");
    setSendError(null);
    setPending((prev) => [...prev, { client_message_id: id, body, status: "sending" }]);
    dispatch(id, body);
  };

  const onRetry = (p: PendingMessage): void => {
    setSendError(null);
    setPending((prev) =>
      prev.map((x) => (x.client_message_id === p.client_message_id ? { ...x, status: "sending" } : x)),
    );
    // Same client_message_id: if the first attempt actually committed, the
    // backend replays the original message instead of creating a duplicate.
    dispatch(p.client_message_id, p.body);
  };

  const onDiscard = (p: PendingMessage): void => {
    setSendError(null);
    setPending((prev) => prev.filter((x) => x.client_message_id !== p.client_message_id));
  };

  if (conversation.isLoading || me.isLoading) {
    return (
      <Screen scroll={false}>
        <Loading label="Opening your chat…" />
      </Screen>
    );
  }

  if (conversation.error) {
    return (
      <Screen>
        <Heading>Chat</Heading>
        <ErrorText>{userMessageFor(conversation.error)}</ErrorText>
        <Button
          title="Try again"
          variant="secondary"
          testID="retry-conversation"
          onPress={() => void conversation.refetch()}
          loading={conversation.isRefetching}
        />
      </Screen>
    );
  }

  if (!conversation.data) {
    return (
      <Screen>
        <Heading>Chat</Heading>
        <Body muted>Chat opens once you are connected with a partner.</Body>
        <Link href="/(app)/home" accessibilityRole="link" testID="go-home">
          <Body>Back to home.</Body>
        </Link>
      </Screen>
    );
  }

  const myUserId = me.data?.id;

  const renderItem = ({ item }: { item: ChatListItem }): React.ReactElement =>
    item.kind === "server" ? (
      <MessageBubble message={item.message} own={item.message.sender_user_id === myUserId} />
    ) : (
      <PendingBubble pending={item.pending} onRetry={onRetry} onDiscard={onDiscard} />
    );

  const keyFor = (item: ChatListItem): string =>
    item.kind === "server" ? item.message.message_id : `pending-${item.pending.client_message_id}`;

  return (
    <Screen scroll={false}>
      <KeyboardAvoidingView
        style={styles.fill}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {messages.isLoading ? (
          <Loading label="Loading messages…" />
        ) : messages.error && server.length === 0 ? (
          <View style={styles.centerBox}>
            <ErrorText>{userMessageFor(messages.error)}</ErrorText>
            <Button
              title="Try again"
              variant="secondary"
              testID="retry-messages"
              onPress={() => void messages.refetch()}
              loading={messages.isRefetching}
            />
          </View>
        ) : items.length === 0 ? (
          <View style={styles.centerBox} testID="chat-empty">
            <Body muted>No messages yet. Say hello!</Body>
          </View>
        ) : (
          <FlatList
            testID="message-list"
            accessibilityLabel="Messages"
            style={styles.fill}
            contentContainerStyle={styles.listContent}
            // Inverted list with reversed data keeps the newest message pinned
            // to the bottom without scroll-position bookkeeping.
            inverted
            data={items.slice().reverse()}
            keyExtractor={keyFor}
            renderItem={renderItem}
          />
        )}

        {sendError ? <ErrorText>{sendError}</ErrorText> : null}

        <View style={styles.composer}>
          <TextInput
            testID="composer-input"
            accessibilityLabel="Message"
            placeholder="Write a message"
            placeholderTextColor={colors.muted}
            style={styles.composerInput}
            value={draft}
            onChangeText={setDraft}
            multiline
            maxLength={4000}
          />
          <Button
            title="Send"
            testID="send-message"
            onPress={onSend}
            disabled={!draft.trim()}
          />
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}

function MessageBubble({ message, own }: { message: MessageResponse; own: boolean }): React.ReactElement {
  const deleted = message.deleted || message.body === null;
  return (
    <View
      testID={`message-${message.client_message_id}`}
      accessibilityLabel={deleted ? "Deleted message" : `${own ? "You" : "Partner"}: ${message.body}`}
      style={[styles.bubble, own ? styles.bubbleOwn : styles.bubbleOther]}
    >
      {deleted ? (
        <Text style={styles.tombstone}>Message deleted</Text>
      ) : (
        <Text style={own ? styles.bubbleTextOwn : styles.bubbleText}>{message.body}</Text>
      )}
    </View>
  );
}

function PendingBubble({
  pending,
  onRetry,
  onDiscard,
}: {
  pending: PendingMessage;
  onRetry: (p: PendingMessage) => void;
  onDiscard: (p: PendingMessage) => void;
}): React.ReactElement {
  return (
    <View
      testID={`pending-${pending.client_message_id}`}
      style={[styles.bubble, styles.bubbleOwn, pending.status === "failed" && styles.bubbleFailed]}
    >
      <Text style={styles.bubbleTextOwn}>{pending.body}</Text>
      {pending.status === "sending" ? (
        <Text style={styles.pendingLabel} accessibilityLiveRegion="polite">
          Sending…
        </Text>
      ) : (
        <View style={styles.failedRow}>
          <Text style={styles.failedLabel} accessibilityRole="alert">
            Not sent
          </Text>
          <Button
            title="Retry"
            variant="secondary"
            testID={`retry-${pending.client_message_id}`}
            onPress={() => onRetry(pending)}
          />
          <Button
            title="Discard"
            variant="secondary"
            testID={`discard-${pending.client_message_id}`}
            onPress={() => onDiscard(pending)}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  centerBox: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, padding: 24 },
  listContent: { paddingVertical: 8, gap: 8 },
  bubble: {
    maxWidth: "82%",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 6,
  },
  bubbleOwn: { alignSelf: "flex-end", backgroundColor: colors.primary },
  bubbleOther: {
    alignSelf: "flex-start",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleFailed: { backgroundColor: colors.disabled },
  bubbleText: { fontSize: 16, lineHeight: 22, color: colors.text },
  bubbleTextOwn: { fontSize: 16, lineHeight: 22, color: colors.primaryText },
  tombstone: { fontSize: 15, fontStyle: "italic", color: colors.muted },
  pendingLabel: { fontSize: 12, color: colors.primaryText, opacity: 0.8 },
  failedLabel: { fontSize: 13, fontWeight: "600", color: colors.danger },
  failedRow: { gap: 6 },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    paddingTop: 8,
  },
  composerInput: {
    flex: 1,
    minHeight: 48,
    maxHeight: 140,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.surface,
  },
});
