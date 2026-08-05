/**
 * Invitation-token normalization and validation.
 *
 * A token is an opaque, URL-safe secret. This module NEVER logs it. It accepts
 * only a bounded, URL-safe character set so that pasted junk, surrounding text,
 * whitespace, or an entire link cannot masquerade as a token. Callers get back
 * either a clean token or `null`; they must not "guess" a token out of arbitrary
 * text.
 */

/** URL-safe token: base64url / hex / uuid-ish, bounded to a sane length. */
const TOKEN_RE = /^[A-Za-z0-9_-]{16,512}$/;

/**
 * Normalize a raw invitation token candidate.
 *
 * Trims surrounding whitespace and a single pair of wrapping quotes/brackets a
 * share sheet might add, then validates the charset and length. Returns the
 * clean token, or `null` if the input is not a well-formed bare token.
 *
 * It deliberately does NOT try to extract a token from a sentence of extra
 * text — that ambiguity is rejected. For a full link, use the deep-link parser,
 * which reads the `token` query parameter unambiguously.
 */
export function normalizeInvitationToken(raw: string | null | undefined): string | null {
  if (typeof raw !== "string") return null;
  let v = raw.trim();
  // Strip a single layer of common wrapping characters from copy/paste.
  v = v.replace(/^["'<([{]+/, "").replace(/["'>)\]}]+$/, "").trim();
  if (!TOKEN_RE.test(v)) return null;
  return v;
}

/** True when `raw` is already a well-formed bare token. */
export function isValidInvitationToken(raw: string | null | undefined): boolean {
  return normalizeInvitationToken(raw) !== null;
}
