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

**Current state:** implementation is authorized, but benchmark execution is not. The implementation must be a
separate draft PR, use no benchmark seed, and remain unmerged until independent audit. No smoke, development,
reserved, scientific, transfer, efficiency, or production conclusion is authorized.
