# Unseen-identifier copy & selection probe — shortcut analysis (DRAFT, documentation-only)

**Documentation-only.** Enumerates the structure-blind baselines that must be measured **before**
reserved execution and shown to sit at chance on their relevant split (numeric bound
`APPROVAL_REQUIRED_BEFORE_EXECUTION`, fixed at protocol-lock). Any baseline exceeding
chance + bound requires investigation **before** reserved execution; the probe is **not** adjusted
after inspecting reserved results.

Preserves `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

## Why shortcuts matter here
The whole point of the probe is to test a genuine copy/selection operation. If a structure-blind
heuristic can score above chance, the split does not isolate the operation and must be re-designed
**before** any reserved run — never patched afterward.

## Required baselines (each ≤ chance + bound on its relevant split)
| Baseline | Description | Relevant splits |
|---|---|---|
| **first-target** | Always return the first `target` listed | C2, C3 |
| **last-target** | Always return the last `target` listed | C2, C3 |
| **most-frequent-target** | Return the target that appears most often across the cohort | C2, C3 |
| **fixed-position** | Return the token at a fixed context position | C1–C4 |
| **lexical-similarity** | Return the candidate most character-similar to the query id | C2, C3, C5 |
| **prefix-matching** | Return the candidate sharing the longest prefix with the query id | C2, C3, C5 |
| **source-target co-occurrence memorization** | Predict the target most often paired with the source in training | C6 vs C7 |
| **training-ID frequency** | Prefer identifiers seen frequently in training | C6, C7 |
| **constant-abstention** | Always abstain | C8 (and must not score on C1–C7) |
| **output-template leakage** | Exploit any fixed output-shape regularity to guess | all |

## Requirements
- **chance is computed mechanically per split** (e.g. 1 / candidate-count for selection splits;
  effectively 0 for exact-sequence copy of an opaque unseen id).
- Each baseline must (a) be ≤ chance + bound on its split, (b) fall **below** the learned
  competence floor, and (c) be **incapable** of satisfying any `..._CONFIRMED` outcome.
- All baselines are measured on **development** cohorts before reserved execution. A failing
  baseline blocks reserved execution until the split is re-designed; **no post-reserved
  adjustment**.
- The **seen-ID control (C6)** exists precisely so co-occurrence / frequency shortcuts can be
  distinguished from genuine generalization on the unseen final pool (C7).

## Identifier-shape guards
Because identifiers are opaque and randomly drawn from a frozen alphabet with a frozen length /
tokenizer-decomposition distribution, and answers are never encoded in prefixes or shape,
lexical-similarity / prefix-matching / template-leakage baselines are expected at chance by
construction. This document commits to **measuring** them anyway before reserved execution rather
than assuming it.
