# Fallback Planning

`build_fallback_plan` selects, for each primary assignment, an ordered set of
fallbacks drawn ONLY from the same role's pinned P1-eligible ranked candidates
(never the primary). Each fallback is permission-feasible and satisfies the policy's
residency / authority (and optional security) equivalence. Ordering prefers
failure-domain diversity vs the primary, then rank; depth ≤ `maximum_fallback_depth`.

States: `COMPLETE` (depth filled), `PARTIAL` (some but fewer than depth),
`NO_FALLBACK_AVAILABLE` (no eligible alternative or none feasible), `NOT_REQUIRED`
(depth 0). A missing fallback is reported honestly — coverage is never manufactured.

Fallback planning is **offline**: it never observes live availability and never
performs runtime reassignment (that is H16/runtime, see H16_RUNTIME_BOUNDARY.md).
