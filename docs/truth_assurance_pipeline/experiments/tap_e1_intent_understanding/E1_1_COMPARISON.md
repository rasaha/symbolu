# TAP-E1.1 — Deterministic vs LLM-Backed Interpreter Comparison

All numbers are on the **new v1.1 corpus**, scored with the (corrected, uniform)
TAP-E1 metric code. "LLM" = in-session agent model (`claude-opus-4-8`) cores composed
with the frozen TAP-E1 layers; "DET" = the frozen TAP-E1 deterministic interpreter.

> Read every number through the **primary limitation**: the same in-session model
> authored the corpus and produced the LLM interpretations (author==interpreter
> confound), and the locked eval was **seen by the interpreter** (not double-blind).
> This is architectural-integration evidence, not independent model validation. See the
> [experiment report](./E1_1_EXPERIMENT_REPORT.md) §2 and §5.

## Locked eval (24) — scoring-frozen, seen by the interpreter

| metric | A raw | B schema | C +extract | D +prov | E +ambig | F +clarify | DET V4 | DET V0 |
|---|---|---|---|---|---|---|---|---|
| objective_accuracy | 0.83 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 1.00 | 1.00 |
| task_type_accuracy | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.375 | 0.375 |
| entity_recall | 0.06 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.19 | 0.06 |
| constraint_preservation | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.60 | 0.00 |
| material_ambiguity_recall | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 0.00 | 0.00 |
| unsupported_assumption_rate | 0.71 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.083 | 0.625 |
| provenance_completeness | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 |
| unnecessary_clarification | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.23 | 0.00 | 0.00 |
| status_accuracy | 0.88 | 1.00 | 1.00 | 1.00 | 0.96 | 0.71 | 0.83 | 0.88 |
| **severe_failures** | 30 | 0 | 0 | 0 | 0 | 1 | 7 | 31 |

## Adversarial (12)

| metric | A raw | D (selected) | E | F | DET V4 |
|---|---|---|---|---|---|
| material_ambiguity_recall | 0.00 | 1.00 | 1.00 | 0.92 | 0.42 |
| unsupported_assumption_rate | 1.00 | 0.00 | 0.00 | 0.083 | 0.58 |
| status_accuracy | 0.00 | 1.00 | 0.75 | 0.50 | 0.17 |
| **severe_failures** | 19 | 0 | 0 | 1 | 7 |

## Negative controls (12)

| metric | A raw | D | E | F | DET V4 |
|---|---|---|---|---|---|
| constraint_preservation | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| unnecessary_clarification | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **severe_failures** | 12 | 0 | 0 | 0 | 0 |

## Readings

1. **The LLM-backed configuration closes the deterministic extractor's generalization gap.** On
   naturally-phrased constraints the deterministic interpreter preserves only 60% (eval)
   / 55% (dev) of explicit constraints; the LLM core preserves 100%. This is the central
   positive result and the reason the deterministic layer alone was insufficient.

2. **Structure is essential even for a strong model.** Raw LLM (A) is the *worst*
   configuration on safety (30 severe on eval, 19 on adversarial, unsupported 0.71–1.00)
   because free text has no schema, no provenance, and no span discipline. The
   IntentRecord schema (B) is what converts a capable model into a safe interpreter.

3. **Deterministic layers add value at ~zero model cost.** B→C→D add extraction and
   provenance with no extra model call (identical token cost); D reaches full provenance
   completeness. Selected config **D**.

4. **The model's own status judgments already cover ambiguity here**, so the
   deterministic ambiguity layer (E) adds little over D on this corpus, and the
   clarification-asking layer (F) *regresses* (over-asks, 0.23 unnecessary; material
   recall 0.5) — consistent with the TAP-E1 finding that the full clarification policy
   is not free.

5. **Under the conditions tested, the LLM-backed configuration is much safer on
   adversarial manipulation** than the deterministic detector (0 vs 7 severe; unsupported
   0.00 vs 0.58): the interpretation core flagged naturally-phrased false premises ("as
   approved", "the usual files") that the lexical detector commits to. Because the same
   model authored these adversarial prompts, this shows the architecture *carries through*
   the model's caution — not that the model has independently validated adversarial
   robustness.
