# Single-hop typed-vs-prose — protocol-lock checklist

Overall state: **`PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`**.

Protocol verdict: **`TYPED_VS_PROSE_PROTOCOL_LOCKED`**.

The protocol is fully specified. Nothing in this checklist authorizes implementation, dataset generation,
training, smoke/development/reserved execution, or production use.

| # | Item | Status |
|---|---|---|
| 1 | Exact B0 grammar frozen | ✅ PASS — operation-specific query templates; fixed fact order, punctuation, missing/conflict/cross-tenant forms; no serializer search |
| 2 | Exact B1 schema frozen | ✅ PASS — required five top-level fields, fixed query/entity/relation/evidence shapes and ordering, no answer/evaluator fields |
| 3 | Paired examples provided | ✅ PASS — S1–S8 and A1–A6 B0↔B1 examples over identical query semantics and fact graphs |
| 4 | Shared output contract frozen | ✅ PASS — one seven-field contract; identical parser/evaluator; no arm-specific post-processing |
| 5 | Existing model recipe identified | ✅ PASS — source-locked `symbolu_neural.clean_softmax` baseline at default commit `0c63d1f2` |
| 6 | Same parameter count confirmed by design | ✅ PASS — same baseline class/config/tokenizer/vocabulary head for B0 and B1; byte-identical paired initialization required |
| 7 | No arm-specific model component | ✅ PASS — no typed encoder/head; representation is the only arm variable |
| 8 | Model architecture and training recipe frozen | ✅ PASS — 64D, 2 layers, 4 heads, 256 FFN, 2304 max sequence, AdamW, 1200 steps, greedy decode |
| 9 | Numeric gates frozen | ✅ PASS — validated/partial/not-found plus causal/evidence/tenant thresholds fixed |
| 10 | Outcome mapping frozen | ✅ PASS — exact `TYPED_STRUCTURE_SINGLE_HOP_*` vocabulary with hard tenant/evidence/protocol/resource outcomes |
| 11 | Causal gates frozen | ✅ PASS — A1–A6 with fixed decline, abstention, evidence, tenant, and decoy thresholds |
| 12 | Tenant hard gate frozen | ✅ PASS — any unauthorized cross-tenant inclusion is a hard failure and never partial |
| 13 | Evidence hard gate frozen | ✅ PASS — precision/recall ≥0.90, causal permutation response, zero unsupported evidence |
| 14 | Token-budget policy frozen | ✅ PASS — 2048 shared character-token input cap, 2304 full sequence, complete fact sets, no truncation/padding |
| 15 | Primary and sensitivity cohorts defined | ✅ PASS — complete information-equivalent cohort primary; ≤10% token-difference subset non-overriding with minimum-count disclosure |
| 16 | Seed roles frozen | ✅ PASS — 76 smoke, 760–762 development, 7160–7164 reserved final |
| 17 | Seed semantics and ordering frozen | ✅ PASS — domain-separated sub-seed rule and no early reserved access |
| 18 | Episode counts and distractor density frozen | ✅ PASS — six domains, per-split cohort counts, four-entity/two-relation/two-evidence S1–S7 density, bounded S8 density |
| 19 | Compute limits frozen | ✅ PASS — one recipe/serializer/schema, ≤2000 steps per arm-run, ≤18 arm-runs, ≤36k aggregate steps, ≤24h |
| 20 | Information-equivalence verifier specified | ✅ PASS — canonicalize both arms to one graph; fail closed |
| 21 | Fact-set and presentation hashes specified | ✅ PASS — both B0/B1 digests must match for 100% of pairs |
| 22 | Deterministic replay requirements specified | ✅ PASS — serialization, init, vocabulary, data/batch order, evaluator, and artifact hashes |
| 23 | Shortcut baselines specified | ✅ PASS — eight baselines, each ≤ chance+0.05 and unable to satisfy validated gates |
| 24 | Scope and invariants preserved | ✅ PASS — documentation-only; no implementation/execution; three standing invariants unchanged |

**Conclusion:** 24/24 requirements pass. The selected clean-softmax model already exists; the benchmark-specific
paired generator, masked-loss harness, parser, evaluator, and reports remain future implementation work and
are not authorized here.

`TYPED_VS_PROSE_PROTOCOL_LOCKED`

The controlled single-hop typed-versus-prose benchmark protocol is fully specified. Implementation and
execution remain unauthorized.
