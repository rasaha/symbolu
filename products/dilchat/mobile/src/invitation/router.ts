/**
 * Pure navigation policy for a pending invitation.
 *
 * Given the current auth status and any pending invitation, decide the single
 * next navigation action. Kept pure so every branch (cold start, signed-out →
 * authenticate → resume, signed-in fast path) is unit-tested without a navigator.
 *
 * INVARIANTS enforced here:
 * - A deep link NEVER lands on the accept mutation. The only signed-in
 *   destination is the CONSENT review screen, so consent can never be bypassed.
 * - While auth is still restoring ("loading"), we wait — we never flash a
 *   signed-out screen for a link that belongs to an already-authenticated user.
 * - Signed-out with a pending invitation routes to sign-in; the pending context
 *   is preserved (in the in-memory store) and resumed once status flips.
 */
import type { AuthStatus } from "@/auth/AuthContext";
import type { PendingInvitation } from "@/invitation/pendingInvitation";

export type InvitationNavAction =
  | { type: "none" }
  | { type: "to-sign-in" }
  | { type: "to-consent"; token: string };

export function decideInvitationNav(
  status: AuthStatus,
  pending: PendingInvitation | null,
): InvitationNavAction {
  if (!pending) return { type: "none" };
  if (status === "loading") return { type: "none" };
  if (status === "signed-out") return { type: "to-sign-in" };
  return { type: "to-consent", token: pending.token };
}
