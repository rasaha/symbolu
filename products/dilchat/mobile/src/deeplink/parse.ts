/**
 * Versioned, validated deep-link parsing for DilChat.
 *
 * SECURITY MODEL
 * - The ONLY thing a deep link may express is "review this pairing invitation".
 *   There is no generic route dispatcher: an unrecognized path is IGNORED, never
 *   navigated to. This forecloses open-redirect / arbitrary-internal-route
 *   attacks — a link can never deep-jump to, say, settings or a signed-in shell.
 * - Only the app's own custom scheme (`dilchat://`) and an explicitly configured
 *   set of HTTPS hosts are trusted. `http://` and unknown hosts are rejected
 *   (no cleartext, no open redirect).
 * - The link is VERSIONED. An unknown version is rejected rather than guessed,
 *   so a future link format can never be misread by an old client.
 * - The token is validated (charset + length) and NEVER logged.
 *
 * The parser is pure and runtime-free so it can be exhaustively unit-tested; the
 * navigation decision (where to send the user, and how to preserve context
 * across authentication) lives in the invitation router, not here.
 */
import { normalizeInvitationToken } from "@/invitation/token";
import { getTrustedInvitationLinkHosts } from "@/config/env";

/** The app's own URL scheme; MUST match `scheme` in app.config.js (guarded by check:config). */
export const APP_SCHEME = "dilchat";

/** Link-format versions this client understands. */
export const SUPPORTED_INVITATION_LINK_VERSIONS = [1] as const;
export type InvitationLinkVersion = (typeof SUPPORTED_INVITATION_LINK_VERSIONS)[number];

/** The newest link version this client emits. */
export const LATEST_INVITATION_LINK_VERSION: InvitationLinkVersion = 1;

/**
 * The only intent a deep link can carry. Deliberately `invitation` (not
 * `invite`): it must NOT collide with the filesystem routes `/invite` (create)
 * or `/accept`, so expo-router's automatic linking never auto-opens a real
 * screen from an external link — our interceptor owns invitation links and
 * routes them through the consent gate.
 */
export const INVITATION_PATH_SEGMENT = "invitation";

export type DeepLinkRejectReason =
  | "empty"
  | "unparseable"
  | "unknown-scheme"
  | "cleartext-scheme"
  | "untrusted-host"
  | "not-an-invitation-route"
  | "unsupported-version"
  | "missing-token"
  | "malformed-token";

export type ParsedDeepLink =
  | { kind: "invitation"; version: InvitationLinkVersion; token: string }
  | { kind: "ignored"; reason: DeepLinkRejectReason };

function ignored(reason: DeepLinkRejectReason): ParsedDeepLink {
  return { kind: "ignored", reason };
}

/** Split "authority/path?query#frag" — deterministic, without URL()'s custom-scheme quirks. */
function splitSchemeless(rest: string): { pathPart: string; query: string } {
  // Drop a fragment first so a token can never hide in "#...".
  const hashless = rest.split("#", 1)[0] ?? "";
  const qIdx = hashless.indexOf("?");
  if (qIdx === -1) return { pathPart: hashless, query: "" };
  return { pathPart: hashless.slice(0, qIdx), query: hashless.slice(qIdx + 1) };
}

function parseQuery(query: string): Map<string, string> {
  const out = new Map<string, string>();
  if (!query) return out;
  for (const pair of query.split("&")) {
    if (!pair) continue;
    const eq = pair.indexOf("=");
    const rawKey = eq === -1 ? pair : pair.slice(0, eq);
    const rawVal = eq === -1 ? "" : pair.slice(eq + 1);
    let key: string;
    let val: string;
    try {
      key = decodeURIComponent(rawKey.replace(/\+/g, " "));
      val = decodeURIComponent(rawVal.replace(/\+/g, " "));
    } catch {
      // A malformed percent-escape is treated as a non-match, never a crash.
      continue;
    }
    // First value wins; ignore duplicate keys (a duplicated token param is not
    // a signal to try both — it is treated as the first value only).
    if (!out.has(key)) out.set(key, val);
  }
  return out;
}

/** Non-empty, slash-delimited path segments. */
function pathSegments(pathPart: string): string[] {
  return pathPart.split("/").filter((s) => s.length > 0);
}

function parseVersion(raw: string | undefined): InvitationLinkVersion | null {
  if (raw === undefined || raw === "") return null;
  if (!/^\d{1,4}$/.test(raw)) return null;
  const n = Number(raw);
  return (SUPPORTED_INVITATION_LINK_VERSIONS as readonly number[]).includes(n)
    ? (n as InvitationLinkVersion)
    : null;
}

/**
 * Parse a deep link into a validated invitation intent, or an `ignored` result
 * with a machine-readable reason. Never throws. Never logs the token.
 *
 * Accepted shapes (query order irrelevant):
 *   dilchat://invite?v=1&token=<token>
 *   https://<trusted-host>/invite?v=1&token=<token>
 * Aliases: `version` for `v`, `t` for `token`.
 */
export function parseDeepLink(
  input: string | null | undefined,
  trustedHosts: string[] = getTrustedInvitationLinkHosts(),
): ParsedDeepLink {
  if (typeof input !== "string" || input.trim() === "") return ignored("empty");
  const url = input.trim();

  const schemeMatch = /^([a-zA-Z][a-zA-Z0-9+.-]*):\/\/(.*)$/.exec(url);
  if (!schemeMatch) return ignored("unparseable");
  const scheme = (schemeMatch[1] ?? "").toLowerCase();
  const rest = schemeMatch[2] ?? "";

  let segments: string[];
  if (scheme === APP_SCHEME) {
    // Custom scheme: authority ("invite") and any path segments both count.
    const { pathPart, query } = splitSchemeless(rest);
    segments = pathSegments(pathPart);
    return finishInvitation(segments, parseQuery(query));
  }
  if (scheme === "http") return ignored("cleartext-scheme");
  if (scheme === "https") {
    // Universal/app link: first segment is the host, which must be trusted.
    const { pathPart, query } = splitSchemeless(rest);
    const all = pathSegments(pathPart);
    const host = (all[0] ?? "").toLowerCase().split(":")[0] ?? ""; // strip any :port
    const allow = new Set(trustedHosts.map((h) => h.toLowerCase()));
    if (!host || !allow.has(host)) return ignored("untrusted-host");
    segments = all.slice(1);
    return finishInvitation(segments, parseQuery(query));
  }
  return ignored("unknown-scheme");
}

function finishInvitation(segments: string[], q: Map<string, string>): ParsedDeepLink {
  // Route allowlist: the ONLY recognized destination is the invitation intent.
  const first = segments[0];
  if (first === undefined || first.toLowerCase() !== INVITATION_PATH_SEGMENT) {
    return ignored("not-an-invitation-route");
  }
  const version = parseVersion(q.get("v") ?? q.get("version"));
  if (version === null) return ignored("unsupported-version");

  const rawToken = q.get("token") ?? q.get("t");
  if (rawToken === undefined || rawToken === "") return ignored("missing-token");
  const token = normalizeInvitationToken(rawToken);
  if (token === null) return ignored("malformed-token");

  return { kind: "invitation", version, token };
}

/**
 * Build a shareable invitation deep link for the app's own scheme. The token is
 * URL-encoded. Used by the invite (share) screen so links are always emitted in
 * the current, parseable, versioned format.
 */
export function buildInvitationLink(
  token: string,
  version: InvitationLinkVersion = LATEST_INVITATION_LINK_VERSION,
): string {
  return `${APP_SCHEME}://${INVITATION_PATH_SEGMENT}?v=${version}&token=${encodeURIComponent(token)}`;
}

/** A user-facing, token-free explanation for an ignored invitation link. */
export function reasonMessage(reason: DeepLinkRejectReason): string {
  switch (reason) {
    case "unsupported-version":
      return "This invitation link was made by a newer version of the app. Please update DilChat and try again.";
    case "missing-token":
    case "malformed-token":
    case "not-an-invitation-route":
    case "unparseable":
      return "This invitation link doesn't look valid. Ask your partner to share it again.";
    case "untrusted-host":
    case "cleartext-scheme":
    case "unknown-scheme":
      return "This link can't be opened by DilChat.";
    case "empty":
      return "There was no invitation link to open.";
  }
}
