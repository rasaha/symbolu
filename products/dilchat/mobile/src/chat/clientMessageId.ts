/**
 * Client message ids: the idempotency key for message creation, scoped by the
 * backend to (conversation, sender, client_message_id). A retry after a
 * timeout MUST reuse the same id so the backend replays the original message
 * instead of duplicating it.
 *
 * Format: `m.<millis base36>.<2 random base36 chunks>` — always matches the
 * backend pattern ^[A-Za-z0-9._:\-]{1,64}$ and stays well under 64 chars.
 * Uniqueness only needs to hold per sender per conversation, so a
 * timestamp + random suffix is sufficient; no crypto dependency is added.
 */

const ALLOWED = /^[A-Za-z0-9._:-]{1,64}$/;

export function newClientMessageId(now: () => number = Date.now): string {
  const chunk = (): string => Math.floor(Math.random() * 36 ** 6).toString(36).padStart(6, "0");
  const id = `m.${now().toString(36)}.${chunk()}${chunk()}`;
  if (!ALLOWED.test(id)) throw new Error("generated client_message_id is invalid");
  return id;
}

export function isValidClientMessageId(id: string): boolean {
  return ALLOWED.test(id);
}
