/**
 * Pure display-model merge for the chat screen: confirmed server messages
 * (ascending server_sequence) plus locally pending sends that the server has
 * not yet echoed back. Pure and side-effect free so it is unit-testable
 * without rendering.
 *
 * Rules:
 * - server messages always win: a pending entry whose client_message_id
 *   appears in the server list is dropped (the send, or an idempotent replay
 *   of it, was confirmed);
 * - remaining pending entries render after all confirmed messages, in the
 *   order they were queued (they have no server_sequence yet);
 * - tombstones stay in place: a deleted message keeps its row with body null.
 */
import type { MessageResponse } from "@/api/types";

export type PendingStatus = "sending" | "failed";

export interface PendingMessage {
  client_message_id: string;
  body: string;
  status: PendingStatus;
}

export type ChatListItem =
  | { kind: "server"; message: MessageResponse }
  | { kind: "pending"; pending: PendingMessage };

export function mergeMessages(
  server: MessageResponse[],
  pending: PendingMessage[],
): ChatListItem[] {
  const confirmed = new Set(server.map((m) => m.client_message_id));
  const items: ChatListItem[] = server.map((message) => ({ kind: "server", message }));
  for (const p of pending) {
    if (!confirmed.has(p.client_message_id)) items.push({ kind: "pending", pending: p });
  }
  return items;
}

/** Highest confirmed sequence in a message list (0 when empty). */
export function latestSequence(server: MessageResponse[]): number {
  let max = 0;
  for (const m of server) if (m.server_sequence > max) max = m.server_sequence;
  return max;
}
