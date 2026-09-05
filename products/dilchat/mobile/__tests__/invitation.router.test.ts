import { decideInvitationNav } from "@/invitation/router";
import type { PendingInvitation } from "@/invitation/pendingInvitation";

const PENDING: PendingInvitation = { token: "a".repeat(40), version: 1, receivedAt: 1 };

describe("decideInvitationNav — invitation navigation policy", () => {
  it("does nothing without a pending invitation", () => {
    expect(decideInvitationNav("signed-in", null)).toEqual({ type: "none" });
    expect(decideInvitationNav("signed-out", null)).toEqual({ type: "none" });
    expect(decideInvitationNav("loading", null)).toEqual({ type: "none" });
  });

  it("waits while the session is still restoring (no premature sign-in flash)", () => {
    expect(decideInvitationNav("loading", PENDING)).toEqual({ type: "none" });
  });

  it("routes a signed-out user to sign-in, preserving context for resume", () => {
    expect(decideInvitationNav("signed-out", PENDING)).toEqual({ type: "to-sign-in" });
  });

  it("routes a signed-in user to CONSENT (never a direct accept)", () => {
    expect(decideInvitationNav("signed-in", PENDING)).toEqual({ type: "to-consent", token: PENDING.token });
  });

  it("resumes to consent once status flips from loading→signed-in", () => {
    // Simulate the resume sequence for the same pending invitation.
    expect(decideInvitationNav("loading", PENDING)).toEqual({ type: "none" });
    expect(decideInvitationNav("signed-out", PENDING)).toEqual({ type: "to-sign-in" });
    expect(decideInvitationNav("signed-in", PENDING)).toEqual({ type: "to-consent", token: PENDING.token });
  });
});
