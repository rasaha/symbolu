# Fallback Boundary Audit

- Fallbacks are drawn only from the same role's pinned P1-eligible ranked set
  (P2-I14), exclude the primary (P2-I15), are unique (P2-I15), permission-feasible,
  residency/authority(/optional security)-equivalent, and resolve to the pinned
  snapshot (P2-I16).
- Ordering is deterministic (failure-domain diversity preference, then rank),
  depth-bounded. Missing fallback is reported honestly (`NO_FALLBACK_AVAILABLE` /
  `PARTIAL`); coverage is never manufactured.
- Fallback planning is **offline**: no live-availability lookup, no runtime
  reassignment. Runtime narrowing rule is documentation + plan invariants only
  (see H16_RUNTIME_BOUNDARY.md).
