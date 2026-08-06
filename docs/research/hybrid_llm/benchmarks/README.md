# Hybrid LLM benchmarks — typed-vs-prose (single-hop) index

Controlled single-hop typed-structure-vs-flattened-prose relational benchmark (B0 vs B1). Preserves
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

- **[SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md](SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md)** — draft
  question, hypothesis, arms, S1–S8, A1–A6, ground truth, and information-equivalence plan.
- **[SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md](SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md)** —
  shortcut/leakage threats, guards, and causal-load-bearing requirements.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md)** — blocked protocol
  specification. Current verdict remains **`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`**.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md)**
  — protocol pass/fail checklist.
- **[SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md](SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md)**
  — exact bounded recipe for the non-memory shared-output harness. It also closes two pre-implementation
  defects: S1 answer-ID leakage and indistinguishable task inputs with conflicting labels. Verdict:
  **`IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`**.
- **[SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION_CHECKLIST.md)**
  — authorization checklist and explicit execution prohibitions.
- **[PR1362_AUDIT_AND_MERGE.md](PR1362_AUDIT_AND_MERGE.md)** · **[PR1363_AUDIT_AND_MERGE.md](PR1363_AUDIT_AND_MERGE.md)**
  — earlier audit records.

**Current state:** implementation is authorized with a fixed shared operation contract and reversible
205-token lexical vocabulary, but benchmark execution is not. The implementation must remain a separate draft
PR, use no benchmark seed, and remain unmerged until independent audit. No smoke, development, reserved,
scientific, transfer, efficiency, or production conclusion is authorized.
