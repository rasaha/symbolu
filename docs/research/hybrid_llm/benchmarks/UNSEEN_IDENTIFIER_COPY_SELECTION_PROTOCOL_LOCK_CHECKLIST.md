# Unseen-identifier copy/selection protocol-lock — checklist

Documentation-only. Pass/fail record for the protocol lock. Maximum permitted state:
`PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`.

| # | Item | Status |
|---|---|---|
| 1 | PR #1368 independently audited and **merged before this lock** (merge `872c034c`) | ✅ pass |
| 2 | Exact scientific question frozen (copy + select unseen identifiers, everything else removed) | ✅ pass |
| 3 | C1–C8 task definitions frozen (Decision 4) | ✅ pass |
| 4 | Copy-vs-selection axis (A) frozen (Decision 1) | ✅ pass |
| 5 | Seen-vs-unseen axis (B) frozen (Decision 1) | ✅ pass |
| 6 | Copy-masks-selection rule frozen (low C1 forbids a C2 selection verdict) | ✅ pass |
| 7 | Exact representation-neutral format frozen (Decision 2; no prose-vs-JSON) | ✅ pass |
| 8 | Exact output contract frozen (Decision 5; bare ID / `INSUFFICIENT_EVIDENCE`; no candidate-index) | ✅ pass |
| 9 | Identifier alphabet and disjoint pools frozen (Decision 3) | ✅ pass |
| 10 | Tokenizer behavior documented (identifiers character-visible; `Q7X2` → 4 tokens, verified) | ✅ pass |
| 11 | Model recipe matched to prior merged benchmark (Decision 6; 209,728 params; source hashes) | ✅ pass |
| 12 | No intervention added (no candidate-index / constrained decoding / pointer / copy / ranking head / capacity change) | ✅ pass |
| 13 | Numeric gates frozen (Decision 7) | ✅ pass |
| 14 | Verdict mapping frozen (Decision 8; none emitted now) | ✅ pass |
| 15 | Shortcut thresholds frozen (Decision 9; ≤ chance + 0.05) | ✅ pass |
| 16 | Shortcut precheck required **before** final execution (hard pre-reserved gate) | ✅ pass |
| 17 | Seed disjointness mechanically confirmed (0 external mentions) | ✅ pass |
| 18 | Seed roles frozen (smoke 9070 / dev 9071–9073 / final 90760–90764; not consumed) | ✅ pass |
| 19 | Compute limits frozen (Decision 11) | ✅ pass |
| 20 | Deterministic fingerprints required (Decision 7 integrity block) | ✅ pass |
| 21 | Implementation unauthorized | ✅ enforced |
| 22 | Execution unauthorized | ✅ enforced |
| 23 | Standing invariants preserved (`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`) | ✅ pass |

**Result:** all decision items specified; model recipe reconstructed from merged source without
code/architecture change (not blocked). Verdict:
**`UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCKED`** (implementation and execution not authorized).
