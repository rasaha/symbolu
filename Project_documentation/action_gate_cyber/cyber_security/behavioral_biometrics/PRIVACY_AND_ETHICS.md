# Privacy & Ethics

Privacy is enforced **by construction** in code (`privacy.py`, `collector.py`,
`storage.py`) and checked by tests, not left to policy.

## What is collected

- **Timing** of input events (key press/release, pointer motion/clicks, scroll,
  touch, device motion) at millisecond resolution.
- **Keyboard key *class*** (letter / digit / space / backspace / … — a coarse
  category, never the character) and an optional **salted, content-free key id** used
  only to preserve digraph *timing* structure within a session.
- **Normalized pointer coordinates** and derived kinematics; touch pressure/size;
  device-motion axes where available.
- **Privacy-safe context** (task stage, active-region id, screen id) — identifiers,
  not screen text.
- **Pseudonymous** participant and device-instance ids, plus consent metadata.

## What is NOT collected

- **No raw typed text or characters.** Fields named `char`/`text`/`raw`/`content`/…
  are stripped at ingest and are a schema violation if present.
- **No passwords or sensitive-field content.** Sensitive regions/screens are
  configurable and suppressed (timing may survive; content and key ids do not).
- No screenshots, no window titles, no clipboard, no network capture.

## Identification risk (stated honestly)

Behavioral timing data can still be **re-identifying**. We do **not** claim
irreversible anonymization. Pseudonyms are salted hashes, not anonymity; a salted
per-session key id is a timing-preserving convenience, not a security control, and a
timing side channel may remain. Treat all stored data as personal data.

## Storage, retention, deletion

- Local storage only; files written `0600`. Optional at-rest encryption
  (`storage.py`) uses a **stdlib-only** stream cipher (PBKDF2-HMAC-SHA256 KDF,
  SHA-256 counter keystream, HMAC-SHA256 tag). This is honest
  obfuscation-to-moderate protection, **not an audited AEAD** (no AES/libsodium in
  this environment) — pair it with full-disk encryption for real deployments.
- **Retention**: `SessionStore.purge_older_than(max_age_days, now_epoch)` (the clock
  is passed in, never hidden).
- **Deletion**: `collector delete-session` / `SessionStore.delete_session` best-effort
  overwrites then removes files (SSD wear-leveling / CoW media may retain residue —
  documented, not guaranteed).
- **Redaction**: `collector redact` drops any residual raw content and blanks
  content-bearing fields for sensitive contexts; timing is preserved.

## Derived features exported separately

Derived features (`features.json`) are stored and exportable **separately** from raw
telemetry (`telemetry.jsonl`), so a research release can share features without the
raw event stream.

## Consent

A `Consent` hook (`granted` / `purpose` / `revoked`) is attached to each session.
Real sessions require admissible consent; synthetic fixtures carry
`purpose="synthetic_test"`.

## Intended use & prohibitions

- **Intended**: a research instrumentation pilot to assess whether synchronized,
  quality-controlled behavioral telemetry with repeated-session stability can be
  collected — a precondition for a *later* signal-existence study.
- **NOT authorized**: production authentication, covert monitoring, employee
  surveillance, or any biometric-identity decision. No biometric-validity claim is
  made or supported by this code, and none may be derived from the synthetic
  generators.
