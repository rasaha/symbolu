# BTRR Base-Capability Prerequisite (P0)

**Purpose.** Prove that the frozen plain transformer can perform the mechanical operations the benchmark
presupposes — copying, selecting, emitting the output schema, abstaining on a trivial visible cue —
*before* any R1–R12 result is interpreted as reasoning. This is required because the prior
`unseen_identifier_copy_selection` and `single_hop_typed_vs_prose` copy/selection harnesses were
implemented but **never executed** (execution unauthorized), so base copy/selection capability for this
recipe is empirically **unestablished**.

**Machinery.** P0 uses the **exact same** tokenizer (`LexicalTokenizer`), model
(`StructuredOutputModel` over `SoftmaxTransformerLM`), output-only objective, `greedy_generate`, and
strict structured-output parser as the main experiment. No separate architecture, tokenizer, model,
training, fine-tuning, or checkpoint. P0 contains **no** relational, temporal, or policy reasoning.

## Single-checkpoint invariant (binds P0 to R1–R12)
Per seed there is ONE trained checkpoint. It is frozen, its `parameter_digest` recorded, then evaluated
on P0 and — byte-identically — on R1–R12. No optimizer step, selection, or modification occurs between
P0 and R1–R12. Each final seed is one paired evidence unit: `checkpoint + P0 + R1–R12`. P0 does not
consume a separate final cohort.

## Subtasks and gates (per final seed)
| ID | Subtask | A-priori chance | Gate |
|---|---|---|---|
| B1 | Copy an opaque entity ID from visible context | ≪ 0.05 | ≥ 0.98 |
| B2 | Select one visible entity from a bounded set (trivial visible cue) | ≤ 1/N (N ≤ 12) | ≥ 0.98 |
| B3 | Copy an evidence ID from visible context | ≪ 0.05 | ≥ 0.98 |
| B4 | Reproduce an event ID from visible context | ≪ 0.05 | ≥ 0.98 |
| B5 | Emit the exact structured-output schema (field order, valid JSON) | ~ 0 | ≥ 0.99 |
| B6 | Return a supplied categorical answer token | 1/A | ≥ 0.98 |
| B7 | Abstain with the correct status when a trivial visible flag says "absent" | 0.5 | ≥ 0.98 |

## Decision rule
P0 runs on development **and** final seeds. If **any** subtask falls below **0.95** on a final seed's
frozen checkpoint:

- primary verdict for that seed → `RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY`
- co-emit `BASE_COPY_SELECTION_CAPABILITY_NOT_ESTABLISHED`
- that seed's R1–R12 outputs are stamped `NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION` and MUST NOT
  contribute to `RELATIONAL_REASONING_NOT_FOUND`, `TEMPORAL_REASONING_FAILED`, `POLICY_REASONING_FAILED`,
  or any other reasoning verdict.

A protocol/integrity failure (precedence step 0) takes priority over P0: a result obtained under a
violated protocol is classified `PROTOCOL_VIOLATED`, never as a P0 success or failure.

## Interpretation
If P0 is not established, the experiment reports a **base-capability** limitation of the frozen recipe —
**not** a reasoning failure. It does not claim reasoning is impossible; it claims the mechanical
substrate for these gates was not demonstrated at this recipe.
