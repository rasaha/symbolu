# Hybrid LLM benchmarks — typed-vs-prose (single-hop) index

Controlled single-hop typed-structure-vs-flattened-prose relational benchmark (B0 vs B1). **Documentation
only — no implementation, data generation, training, or execution is authorized.** Preserves
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

- **[SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md](SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md)** — the
  preregistered scientific question, hypothesis, exactly two arms, splits S1–S8, ablations A1–A6,
  deterministic authority, information-equivalence plan, and bounded conclusion vocabulary.
- **[SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md](SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md)** —
  shortcut/leakage threats, mechanical guards, near-chance baselines, causal-load-bearing requirement, and
  tenant-isolation hard gate.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md)** — the complete
  protocol lock: B0 serializer, B1 schema, shared output, source-locked clean-softmax model/training recipe,
  numeric and causal gates, input fairness, seeds, episode counts, distractor density, compute limits,
  paired examples, determinism, and information-equivalence requirements.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md)**
  — 24/24 protocol-lock checklist.
- **[PR1362_AUDIT_AND_MERGE.md](PR1362_AUDIT_AND_MERGE.md)** ·
  **[PR1363_AUDIT_AND_MERGE.md](PR1363_AUDIT_AND_MERGE.md)** — audit records for the thesis-V1.1 and
  preregistration merges.

**Current state:** `PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`.

**Protocol verdict:** `TYPED_VS_PROSE_PROTOCOL_LOCKED`.

The controlled single-hop typed-versus-prose benchmark protocol is fully specified. The selected model is the
existing non-memory `symbolu_neural.clean_softmax` baseline; no architecture change or typed-only component is
required. The paired benchmark generator, training harness, parser, evaluator, reports, and all execution are
future work and remain unauthorized.
