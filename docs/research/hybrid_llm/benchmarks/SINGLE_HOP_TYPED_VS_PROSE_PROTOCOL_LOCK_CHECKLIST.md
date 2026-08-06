# Single-hop typed-vs-prose — protocol-lock checklist

Pass/fail for each protocol-lock requirement. Overall verdict: **`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`** — the
model-recipe item fails (no suitable existing non-memory recipe without code changes), so the protocol is
**not** locked. All other items are specified.

| # | Item | Status |
|---|---|---|
| 1 | Exact B0 grammar frozen | ✅ PASS (Decision 1: fixed order, one grammar, frozen punctuation/orderings, paired examples) |
| 2 | Exact B1 schema frozen | ✅ PASS (Decision 2: fixed JSON contract, deterministic ordering, no answer/validity/gold fields) |
| 3 | Paired examples provided | ✅ PASS (S1–S8 / A1–A6 B0↔B1 pairs over identical canonical fact sets) |
| 4 | Shared output contract frozen | ✅ PASS (one contract; identical parser + evaluator; no arm-specific post-processing) |
| 5 | Model recipe identified | ❌ **FAIL / BLOCKED** (Decision 5: no existing non-memory tokenizer-based from-scratch recipe without code changes) |
| 6 | Same parameter count confirmed by design | ⛔ N/A while blocked (would be guaranteed by a shared base + head once a recipe exists) |
| 7 | No arm-specific model component | ✅ PASS (design mandates shared tokenizer + head; input representation is the only variable) |
| 8 | Numeric gates frozen | ✅ PASS (Decision 3: all validated/partial/not-found/causal/evidence/tenant thresholds fixed) |
| 9 | Outcome mapping frozen | ✅ PASS (`TYPED_STRUCTURE_SINGLE_HOP_*` mapping with hard tenant/evidence failures) |
| 10 | Causal gates frozen | ✅ PASS (A1–A6 with fixed collapse/abstention thresholds) |
| 11 | Tenant hard gate frozen | ✅ PASS (any unauthorized cross-tenant inclusion = hard failure; never "partial") |
| 12 | Evidence hard gate frozen | ✅ PASS (precision/recall ≥ 0.90; permutation causal response; zero unsupported emission) |
| 13 | Token-budget policy frozen | ✅ PASS (Decision 4: 512-token common window; no truncation; report counts; no padding) |
| 14 | Primary and sensitivity cohorts defined | ✅ PASS (complete info-equivalent cohort primary; ≤10%-token subset sensitivity, non-overriding) |
| 15 | Seed roles frozen | ✅ PASS (Decision 6: 76 smoke / 760–762 dev / 7160–7164 reserved, with role limits) |
| 16 | Seed disjointness mechanically checked | ✅ PASS (disjoint; the "76" hit was a false positive in `72.76`/a commit hash) |
| 17 | Compute limits frozen | ✅ PASS (≤1 recipe/serializer/schema; ≤2000 steps/arm/seed; ≤18 arm-runs; ≤36k steps; ≤24h; no restarts/extension) |
| 18 | Information-equivalence verifier specified | ✅ PASS (canonicalize both arms to one fact graph; fail closed) |
| 19 | Fact-set hash specified | ✅ PASS (`B0_fact_hash == B1_fact_hash` required for 100% of pairs) |
| 20 | Deterministic replay requirements specified | ✅ PASS (byte-identical generation/serialization; init/data-order hashes; recorded hashes) |
| 21 | Shortcut baselines specified | ✅ PASS (8 baselines; each ≤ chance+0.05 and below competence floor; cannot satisfy validated) |
| 22 | No implementation authorization | ✅ PASS (explicitly not authorized) |
| 23 | No execution authorization | ✅ PASS (explicitly not authorized) |
| 24 | Invariants preserved | ✅ PASS (`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`) |

**Conclusion:** 22 specified / 1 blocked (item 5) / 1 N/A-pending-recipe (item 6). The single blocker
(model recipe) prevents `TYPED_VS_PROSE_PROTOCOL_LOCKED`; verdict is `PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`.
Unblocking requires a separately authorized implementation step (a minimal non-memory tokenizer-based
transformer with a shared structured-output head + prose-vs-typed harness), reviewed and merged on its own.
