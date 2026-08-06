# Hybrid LLM benchmarks — typed-vs-prose (single-hop) index

Controlled single-hop typed-structure-vs-flattened-prose relational benchmark (B0 vs B1). Preserves
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

- **[SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md](SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md)** — the draft
  design (question, hypothesis, arms, splits S1–S8, ablations A1–A6, ground-truth/info-equivalence, gate
  structure).
- **[SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md](SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md)** —
  shortcut/leakage threats + guards + causal-load-bearing requirement.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md)** — protocol
  specification. Current verdict remains **`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`** until the separately
  authorized implementation exists, passes integrity checks, is independently audited, and is merged.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md)**
  — protocol pass/fail checklist (22 specified · 1 blocked · 1 N/A-pending-recipe).
- **[SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md](SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md)**
  — exact bounded recipe and file/test scope for the new non-memory fixed-lexical-tokenizer shared-output
  harness. Verdict: **`IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`**.
- **[SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION_CHECKLIST.md)**
  — authorization checklist and explicit execution prohibitions.
- **[PR1362_AUDIT_AND_MERGE.md](PR1362_AUDIT_AND_MERGE.md)** · **[PR1363_AUDIT_AND_MERGE.md](PR1363_AUDIT_AND_MERGE.md)**
  — audit records for the thesis-V1.1 and preregistration merges.

- **[SINGLE_HOP_TYPED_VS_PROSE_EXECUTION_AUTHORIZATION.md](SINGLE_HOP_TYPED_VS_PROSE_EXECUTION_AUTHORIZATION.md)**
  — owner authorization record for building the real dataset and executing the frozen protocol.
- **[SINGLE_HOP_TYPED_VS_PROSE_RESULTS.md](SINGLE_HOP_TYPED_VS_PROSE_RESULTS.md)** — executed results and
  verdict: **`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`** (B1 JSON − B0 prose = −0.022 primary; 0/5
  seeds pass; tenant isolation held; information-equivalence and determinism verified). A preregistered null:
  typed structure gave no single-hop advantage at the frozen recipe, and neither representation solved
  copy-from-context on unseen identities.

**Current state:** the benchmark was implemented, frozen, owner-authorized, and executed
(smoke 76 → dev 760–762 → reserved final 7160–7164). Verdict is a clean preregistered null
(`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`). No transfer, efficiency, multi-hop, temporal, memory,
or production conclusion is drawn. Preserves `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`E1_TEMPORAL_TRANSFER_PARTIAL`, `KDA_VALIDATION_BLOCKED`.
