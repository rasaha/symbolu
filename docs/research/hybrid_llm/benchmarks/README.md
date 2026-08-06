# Hybrid LLM benchmarks — typed-vs-prose (single-hop) index

Controlled single-hop typed-structure-vs-flattened-prose relational benchmark (B0 vs B1). **Documentation
only — no implementation, data, training, or execution is authorized.** Preserves
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

- **[SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md](SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md)** — the draft
  design (question, hypothesis, arms, splits S1–S8, ablations A1–A6, ground-truth/info-equivalence, gate
  structure).
- **[SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md](SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md)** —
  shortcut/leakage threats + guards + causal-load-bearing requirement.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md)** — the protocol
  lock resolving Decisions 1–6. **Verdict: `PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`** — Decisions 1/2/3/4/6 are
  fully specified, but Decision 5 (an existing non-memory tokenizer-based from-scratch model recipe) cannot be
  resolved without code changes, so the protocol is **not** locked.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md)**
  — pass/fail checklist (22 specified · 1 blocked · 1 N/A-pending-recipe).
- **[PR1362_AUDIT_AND_MERGE.md](PR1362_AUDIT_AND_MERGE.md)** · **[PR1363_AUDIT_AND_MERGE.md](PR1363_AUDIT_AND_MERGE.md)**
  — audit records for the thesis-V1.1 and preregistration merges.

**Status:** protocol specified on 5/6 decisions; **blocked** on the model recipe. Unblocking requires a
separately authorized implementation step (a minimal non-memory, tokenizer-based, from-scratch transformer
with a shared structured-output head + prose-vs-typed harness), reviewed and merged on its own before any
smoke/dev/reserved run. Nothing here authorizes implementation or execution.
