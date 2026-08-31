import { isValidInvitationToken, normalizeInvitationToken } from "@/invitation/token";

const TOKEN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-ab";

describe("normalizeInvitationToken", () => {
  it("accepts a well-formed URL-safe token", () => {
    expect(normalizeInvitationToken(TOKEN)).toBe(TOKEN);
    expect(isValidInvitationToken(TOKEN)).toBe(true);
  });

  it("trims surrounding whitespace (token copied with extra spaces/newlines)", () => {
    expect(normalizeInvitationToken(`  ${TOKEN}\n`)).toBe(TOKEN);
  });

  it("strips a single layer of wrapping quotes/brackets from a share sheet", () => {
    expect(normalizeInvitationToken(`"${TOKEN}"`)).toBe(TOKEN);
    expect(normalizeInvitationToken(`<${TOKEN}>`)).toBe(TOKEN);
  });

  it("rejects tokens with spaces or extra prose inside", () => {
    expect(normalizeInvitationToken(`here is my code ${TOKEN}`)).toBeNull();
    expect(normalizeInvitationToken(`${TOKEN} extra`)).toBeNull();
  });

  it("rejects too-short, empty, and non-string input", () => {
    expect(normalizeInvitationToken("short")).toBeNull();
    expect(normalizeInvitationToken("")).toBeNull();
    expect(normalizeInvitationToken(null)).toBeNull();
    expect(normalizeInvitationToken(undefined)).toBeNull();
  });

  it("rejects disallowed characters", () => {
    expect(normalizeInvitationToken("a".repeat(20) + "!")).toBeNull();
    expect(normalizeInvitationToken("a".repeat(20) + "/x")).toBeNull();
  });
});
