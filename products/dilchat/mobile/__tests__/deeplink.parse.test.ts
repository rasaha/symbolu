import {
  APP_SCHEME,
  buildInvitationLink,
  parseDeepLink,
  reasonMessage,
  SUPPORTED_INVITATION_LINK_VERSIONS,
} from "@/deeplink/parse";

// 64-char URL-safe token, matching the backend's secrets.token_urlsafe(48).
const TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-ab";

describe("parseDeepLink — valid invitation links", () => {
  it("parses the canonical custom-scheme link", () => {
    const r = parseDeepLink(`${APP_SCHEME}://invitation?v=1&token=${TOKEN}`);
    expect(r).toEqual({ kind: "invitation", version: 1, token: TOKEN });
  });

  it("is order-insensitive and accepts aliases (version, t)", () => {
    const r = parseDeepLink(`${APP_SCHEME}://invitation?t=${TOKEN}&version=1`);
    expect(r).toEqual({ kind: "invitation", version: 1, token: TOKEN });
  });

  it("tolerates a leading slash in the path", () => {
    const r = parseDeepLink(`${APP_SCHEME}:///invitation?v=1&token=${TOKEN}`);
    expect(r).toEqual({ kind: "invitation", version: 1, token: TOKEN });
  });

  it("URL-decodes the token", () => {
    const r = parseDeepLink(`${APP_SCHEME}://invitation?v=1&token=${encodeURIComponent(TOKEN)}`);
    expect(r).toEqual({ kind: "invitation", version: 1, token: TOKEN });
  });

  it("round-trips buildInvitationLink → parseDeepLink", () => {
    const link = buildInvitationLink(TOKEN);
    expect(parseDeepLink(link)).toEqual({ kind: "invitation", version: 1, token: TOKEN });
  });

  it("only supports declared versions", () => {
    expect(SUPPORTED_INVITATION_LINK_VERSIONS).toEqual([1]);
  });
});

describe("parseDeepLink — HTTPS host allowlist (anti open-redirect)", () => {
  it("accepts a trusted https host", () => {
    const r = parseDeepLink(`https://links.dilchat.app/invitation?v=1&token=${TOKEN}`, ["links.dilchat.app"]);
    expect(r).toEqual({ kind: "invitation", version: 1, token: TOKEN });
  });

  it("rejects an untrusted https host", () => {
    const r = parseDeepLink(`https://evil.example.com/invitation?v=1&token=${TOKEN}`, ["links.dilchat.app"]);
    expect(r).toEqual({ kind: "ignored", reason: "untrusted-host" });
  });

  it("rejects https entirely when no host is configured (default)", () => {
    const r = parseDeepLink(`https://links.dilchat.app/invitation?v=1&token=${TOKEN}`, []);
    expect(r).toEqual({ kind: "ignored", reason: "untrusted-host" });
  });

  it("rejects cleartext http", () => {
    const r = parseDeepLink(`http://links.dilchat.app/invitation?v=1&token=${TOKEN}`, ["links.dilchat.app"]);
    expect(r).toEqual({ kind: "ignored", reason: "cleartext-scheme" });
  });
});

describe("parseDeepLink — route allowlist (no arbitrary internal routes)", () => {
  it.each(["home", "settings", "profile", "paired", "(app)/settings", "invite", "accept"])(
    "refuses to route non-invitation path %s",
    (path) => {
      const r = parseDeepLink(`${APP_SCHEME}://${path}?v=1&token=${TOKEN}`);
      expect(r).toEqual({ kind: "ignored", reason: "not-an-invitation-route" });
    },
  );

  it("ignores an unknown scheme", () => {
    expect(parseDeepLink(`otherapp://invitation?v=1&token=${TOKEN}`)).toEqual({
      kind: "ignored",
      reason: "unknown-scheme",
    });
  });
});

describe("parseDeepLink — malformed / version / token errors", () => {
  it("rejects an unsupported (newer) version", () => {
    expect(parseDeepLink(`${APP_SCHEME}://invitation?v=2&token=${TOKEN}`)).toEqual({
      kind: "ignored",
      reason: "unsupported-version",
    });
  });

  it("rejects a missing version", () => {
    expect(parseDeepLink(`${APP_SCHEME}://invitation?token=${TOKEN}`)).toEqual({
      kind: "ignored",
      reason: "unsupported-version",
    });
  });

  it("reports a missing token", () => {
    expect(parseDeepLink(`${APP_SCHEME}://invitation?v=1`)).toEqual({
      kind: "ignored",
      reason: "missing-token",
    });
  });

  it("reports a malformed token (too short / bad charset)", () => {
    expect(parseDeepLink(`${APP_SCHEME}://invitation?v=1&token=short`)).toEqual({
      kind: "ignored",
      reason: "malformed-token",
    });
    expect(parseDeepLink(`${APP_SCHEME}://invitation?v=1&token=${"a".repeat(20)}%20oops`)).toEqual({
      kind: "ignored",
      reason: "malformed-token",
    });
  });

  it("does not read a token hidden in a fragment", () => {
    const r = parseDeepLink(`${APP_SCHEME}://invitation?v=1#token=${TOKEN}`);
    expect(r).toEqual({ kind: "ignored", reason: "missing-token" });
  });

  it.each([["", "empty"], ["not a url", "unparseable"], ["   ", "empty"]] as const)(
    "handles junk input %p → %p",
    (input, reason) => {
      expect(parseDeepLink(input)).toEqual({ kind: "ignored", reason });
    },
  );

  it("never returns a message that contains the token", () => {
    for (const reason of [
      "empty",
      "unparseable",
      "unknown-scheme",
      "cleartext-scheme",
      "untrusted-host",
      "not-an-invitation-route",
      "unsupported-version",
      "missing-token",
      "malformed-token",
    ] as const) {
      expect(reasonMessage(reason)).not.toContain(TOKEN);
      expect(reasonMessage(reason).length).toBeGreaterThan(0);
    }
  });
});
