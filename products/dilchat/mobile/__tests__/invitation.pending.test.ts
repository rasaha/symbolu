import {
  __resetPendingInvitationForTests,
  clearPendingInvitation,
  getPendingInvitation,
  setPendingInvitation,
  subscribePendingInvitation,
} from "@/invitation/pendingInvitation";

const TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-ab";
const TOKEN2 = "ZZZZdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";

describe("pendingInvitation store", () => {
  beforeEach(() => __resetPendingInvitationForTests());

  it("starts empty", () => {
    expect(getPendingInvitation()).toBeNull();
  });

  it("stores and clears the minimum context", () => {
    setPendingInvitation({ token: TOKEN, version: 1 });
    expect(getPendingInvitation()).toMatchObject({ token: TOKEN, version: 1 });
    clearPendingInvitation();
    expect(getPendingInvitation()).toBeNull();
  });

  it("only exposes token + version + a receivedAt tag (no other fields)", () => {
    setPendingInvitation({ token: TOKEN, version: 1 });
    expect(Object.keys(getPendingInvitation() ?? {}).sort()).toEqual(["receivedAt", "token", "version"]);
  });

  it("is idempotent for a repeated identical token (no listener churn)", () => {
    let notifications = 0;
    const unsub = subscribePendingInvitation(() => (notifications += 1));
    setPendingInvitation({ token: TOKEN, version: 1 });
    setPendingInvitation({ token: TOKEN, version: 1 }); // repeated tap of same link
    expect(notifications).toBe(1);
    unsub();
  });

  it("replaces context when a different token arrives (account/link change)", () => {
    setPendingInvitation({ token: TOKEN, version: 1 });
    setPendingInvitation({ token: TOKEN2, version: 1 });
    expect(getPendingInvitation()?.token).toBe(TOKEN2);
  });

  it("notifies subscribers on set and clear", () => {
    const calls: string[] = [];
    const unsub = subscribePendingInvitation(() => calls.push(getPendingInvitation() ? "set" : "clear"));
    setPendingInvitation({ token: TOKEN, version: 1 });
    clearPendingInvitation();
    expect(calls).toEqual(["set", "clear"]);
    unsub();
  });
});
