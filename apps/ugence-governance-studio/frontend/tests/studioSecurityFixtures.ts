// api-allowlist-negative-fixtures — this file intentionally lists forbidden verbs as
// NEGATIVE fixtures; the marker on this line exempts it from the verifier's own
// forbidden-reference scan.
export const CONSOLE_PROHIBITED = [
  "authorize",
  "clear",
  "execute",
  "grant",
] as const;
