/**
 * Pending-invitation store.
 *
 * When a user opens an invitation deep link while signed out (or on cold start),
 * the invitation context must survive the trip through authentication and be
 * resumed afterwards. This store holds ONLY the minimum context — the validated
 * token and link version — and holds it IN MEMORY ONLY.
 *
 * TOKEN MINIMIZATION (privacy):
 * - The token is never written to SecureStore, AsyncStorage, a file, logs,
 *   analytics, or crash breadcrumbs. It lives only for the current app process.
 * - It is cleared on: successful accept, rejection/cancel, backend invalidation,
 *   sign-out, and account switch (sign-out clears it, so a later sign-in as a
 *   different account never inherits it).
 * - Because it is in-memory, a cold app kill also drops it; a link re-open
 *   re-establishes it. It therefore never persists "longer than needed".
 *
 * The store is a tiny external store compatible with `useSyncExternalStore`.
 */
import { useSyncExternalStore } from "react";

import type { InvitationLinkVersion } from "@/deeplink/parse";

export interface PendingInvitation {
  token: string;
  version: InvitationLinkVersion;
  /** Monotonic-ish tag to distinguish re-taps of the same link (in-process only). */
  receivedAt: number;
}

let current: PendingInvitation | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

/**
 * Record a pending invitation. If an identical token is already pending, the
 * store is left unchanged (a repeated tap of the same link is idempotent and
 * does not disturb an in-progress review).
 */
export function setPendingInvitation(next: Omit<PendingInvitation, "receivedAt">): void {
  if (current && current.token === next.token && current.version === next.version) return;
  current = { ...next, receivedAt: nextSeq() };
  emit();
}

export function getPendingInvitation(): PendingInvitation | null {
  return current;
}

/** Clear the pending invitation. Idempotent. Call on accept/reject/invalidate/sign-out/switch. */
export function clearPendingInvitation(): void {
  if (current === null) return;
  current = null;
  emit();
}

export function subscribePendingInvitation(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React hook: current pending invitation (or null), re-rendering on change. */
export function usePendingInvitation(): PendingInvitation | null {
  return useSyncExternalStore(subscribePendingInvitation, getPendingInvitation, getPendingInvitation);
}

// A process-local sequence counter. Avoids Date.now() so behavior is deterministic
// in tests and never depends on wall-clock; only ordering/inequality matters.
let seq = 0;
function nextSeq(): number {
  seq += 1;
  return seq;
}

/** Test-only: reset module state between cases. */
export function __resetPendingInvitationForTests(): void {
  current = null;
  seq = 0;
  listeners.clear();
}
