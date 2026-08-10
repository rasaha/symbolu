# TAP — Evaluation Framework v0.1

How **every layer is evaluated independently**. Architecture-only; defines the
evaluation *design*, asserts **no results**.

> Boundary: `12_RESEARCH_BOUNDARIES.md`. No empirical claim is made here.

---

## 1. Independent-evaluation rule

Each layer is evaluated in isolation against its own ground truth, with its own
metrics and corpora. A layer's score never depends on another layer's implementation
— a prerequisite for independent replaceability.

## 2. Per-layer evaluation spec

| Layer | Inputs | Outputs | Ground truth | Metrics | Failure attribution | Required corpus/experiment |
|---|---|---|---|---|---|---|
| **Intent** | request | scoped query | labeled intents/constraints | intent accuracy; constraint recall | misscope vs dropped constraint | intent corpus |
| **Retrieval** | scoped query | candidate evidence | labeled relevant spans | recall; precision | miss vs distractor | retrieval corpus |
| **L1 relationship** | evidence + proposals | validated/rejected/uncertain | gold relationship labels + spans | precision; recall; direction acc; abstention correctness | false accept vs reject vs direction | relationship-truth corpus |
| **L2 governance** | validated relationships | governing set + operative source | gold applicability + operative source | operative-source acc; conflict-resolution acc; abstention correctness | wrong source vs missed exception | governance-truth corpus (genuine + resolved conflicts) |
| **L3 packet** | L1+L2 | evidence packet | gold minimal complete set | completeness; minimality; provenance coverage | omission vs over-inclusion | packet corpus |
| **L4 claim** | packet + claims | per-claim records | gold claim status | claim precision/recall; per-status acc; leakage-detection | which leakage class missed | claim-truth corpus |
| **L5 response** | draft + claims | validated response | gold faithful answer | faithfulness; citation completeness; over-generalization detection | which response defect | response-truth corpus |

## 3. Cross-cutting evaluations

- **Cross-layer provenance:** fraction of final assertions traceable end-to-end
  (`04_…`).
- **Cross-layer confidence:** calibration of each `ConfidenceVector` dimension
  against realized correctness (`05_…`).
- **Judge decomposition:** per-role marginal contribution via ablation (advocate,
  challenger, deterministic, adjudicator) — as demonstrated (synthetically) for
  Layer 4 in `relationship_claim_validation/`.

## 4. Required experimental hygiene (for any future layer experiment)

1. **One layer at a time.** An experiment evaluates exactly one layer; it modifies no
   other layer (`11_…`).
2. **Held-out / hidden evaluation** with a frozen lock over prompts/rules/schemas/
   thresholds and corpus, before results.
3. **Negative controls** (evidence sufficient — detect over-abstention) and
   **positive controls** (genuine defect present — detect under-detection).
4. **Deterministic reproducibility** where the layer is deterministic; declared
   non-determinism where an LLM judge is used.
5. **Honest corpora provenance:** synthetic vs real must be labeled; self-authored
   ground truth must be flagged as construction-validating, not efficacy-proving.

## 5. What can be evaluated *today*

Only Layer 4, and only on a **self-authored synthetic** corpus with **deterministic**
judges — the existing `relationship_claim_validation/` prototype. That result is
construction/mechanism validation, not evidence of real-world performance
(`12_…`). Every other layer's evaluation is a future experiment (`11_…`) requiring a
corpus that does not yet exist in this repository.
