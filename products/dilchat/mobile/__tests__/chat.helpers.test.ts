import { isValidClientMessageId, newClientMessageId } from "@/chat/clientMessageId";
import { latestSequence, mergeMessages, type PendingMessage } from "@/chat/merge";
import type { MessageResponse } from "@/api/types";

function msg(over: Partial<MessageResponse>): MessageResponse {
  return {
    message_id: "m1",
    conversation_id: "conv1",
    sender_user_id: "u1",
    client_message_id: "cid-1",
    server_sequence: 1,
    body: "hello",
    created_at: "2026-01-01T00:00:00Z",
    deleted: false,
    deleted_at: null,
    ...over,
  };
}

describe("newClientMessageId", () => {
  it("always matches the backend pattern and stays under 64 chars", () => {
    for (let i = 0; i < 500; i++) {
      const id = newClientMessageId();
      expect(isValidClientMessageId(id)).toBe(true);
      expect(id.length).toBeLessThanOrEqual(64);
    }
  });

  it("is unique across rapid generation (same-millisecond ids differ)", () => {
    const now = (): number => 1_700_000_000_000; // frozen clock: randomness must carry uniqueness
    const ids = new Set(Array.from({ length: 1000 }, () => newClientMessageId(now)));
    expect(ids.size).toBe(1000);
  });
});

describe("mergeMessages", () => {
  const pending = (id: string, status: PendingMessage["status"] = "sending"): PendingMessage => ({
    client_message_id: id,
    body: `body-${id}`,
    status,
  });

  it("drops a pending entry once the server echoes its client_message_id", () => {
    const server = [msg({ message_id: "m1", client_message_id: "cid-a", server_sequence: 1 })];
    const items = mergeMessages(server, [pending("cid-a"), pending("cid-b")]);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: "server" });
    expect(items[1]).toMatchObject({ kind: "pending", pending: { client_message_id: "cid-b" } });
  });

  it("keeps confirmed messages in server order and pending entries after them", () => {
    const server = [
      msg({ message_id: "m1", client_message_id: "a", server_sequence: 1 }),
      msg({ message_id: "m2", client_message_id: "b", server_sequence: 2 }),
    ];
    const items = mergeMessages(server, [pending("p1"), pending("p2", "failed")]);
    expect(items.map((i) => (i.kind === "server" ? i.message.message_id : i.pending.client_message_id)))
      .toEqual(["m1", "m2", "p1", "p2"]);
  });

  it("preserves tombstones as rows with a null body", () => {
    const server = [msg({ deleted: true, body: null, deleted_at: "2026-01-02T00:00:00Z" })];
    const items = mergeMessages(server, []);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: "server", message: { deleted: true, body: null } });
  });
});

describe("latestSequence", () => {
  it("returns 0 for an empty list and the max sequence otherwise", () => {
    expect(latestSequence([])).toBe(0);
    expect(
      latestSequence([
        msg({ server_sequence: 3 }),
        msg({ server_sequence: 7 }),
        msg({ server_sequence: 5 }),
      ]),
    ).toBe(7);
  });
});
