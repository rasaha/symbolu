# Explicit-key semantic memory (E1) — execution report

**Primary verdict: `EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`**
**Always co-emitted: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.**
**On pass, additionally: `INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED`.**

A bounded, preregistered B0-vs-E1 capability probe. **Not** a repair of anonymous BindingSlots, **not** a
reliability requirement (the external table already provides reliability), and **KDA remains blocked**.
The verdict reconstructs mechanically from committed evidence; all 17 frozen artifact hashes match; the
frozen `abc.json` (`b31989a3…`) is unchanged.

## Frozen protocol (locked in Stage 2)
`E1_PROTOCOL_LOCKED`. Shared compositional semantic-matching task (identity = pair of entity primitives;
attribute = one primitive; fact → value). Keys use canonical surface forms; queries use different
synonym surface forms + reorder + filler (no verbatim overlap), so success requires **learned semantic
matching**, not surface overlap. Identities partitioned disjointly into train/dev/**final(reserved)**
(774/181/173). Frozen: `D=64`, 1500 train episodes, `STEPS=1800`, `BATCH=48`, `LR=1e-3`, `TAU=0.05`,
32 keys/episode, learned-null-key no-match, hard top-1 value read. Reserved seeds `[2028..2032]`, ≥4/5
must pass, worst-seed G1 floor 0.70.

## Determinism & integrity (pre-reserved gates, both passed)
- **Determinism:** repeated dev fixture byte-identical (E1+B0 param hashes + metrics equal).
- **Leakage/shortcut suite `all_pass`:** zero query↔key surface-token overlap; disjoint identity pools;
  eval identities unseen in training; no value token in any key; a **lexical-overlap matcher scores at
  chance** (surface hashing cannot solve the task); no external-table import in E1 inference.

## Reserved go/no-go (final pool, 5 fresh seeds)

| seed | E1 G1 addr | E1 G1 e2e | B0 G1 e2e | no-match false-accept | all gates |
|---|---|---|---|---|---|
| 2028 | 0.987 | 0.947 | 0.060 | 0.127 | ✅ |
| 2029 | 1.000 | 0.920 | 0.027 | 0.073 | ✅ |
| 2030 | 1.000 | 0.947 | 0.040 | 0.100 | ✅ |
| 2031 | 0.980 | 0.907 | 0.020 | 0.120 | ✅ |
| 2032 | 1.000 | 0.940 | 0.040 | 0.093 | ✅ |
| **all** | **≥0.98** | **~0.93** | **~0.04** | **≤0.13** | **5/5** |

Held-out generalization (mean across seeds, E1): unseen-identity ~0.99, paraphrase ~0.98, hard-names
~0.99, same-entity/diff-attribute ~0.97, recombined ~0.99, stable ~0.99. No-match recall ~0.89,
precision ~0.93. **Mean E1-over-B0 improvement = 0.895.** B0 (anonymous slots) is at chance on every
generalization split and has no abstention.

## What this supports (only)
"The frozen E1 explicit-key dual-encoder bundle learned semantic episode-local key matching with hard
top-1 value retrieval **more reliably than the frozen anonymous BindingSlots baseline** at the
preregistered ~32-key density and held-out generalization conditions." It does **not** establish which
component caused the improvement (a bundle test), repair of anonymous BindingSlots, arbitrary capacity,
versioning, production readiness, long-context reasoning, external-table replacement, or KDA readiness.
See `LIMITATIONS.md`.
