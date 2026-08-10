# E1 — leakage and exact-symbol / memorization shortcut analysis

**Draft analysis for approval; nothing is executed.** Companion to `EXPLICIT_KEY_E1_PREREGISTRATION.md`.
Its purpose: guarantee that any E1 win comes from **learned semantic matching**, not from a disguised
database lookup, a memorized train/eval overlap, evaluator information, or an answer-derived key. If any
prohibited construction is present or any mechanical test fails, the experiment must terminate with
`EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED` (integrity outcome), regardless of accuracy.

## 1. Why this matters

If the key is a clean discrete symbol shared verbatim between write and query and lookup is exact-match,
the "neural memory" degenerates into a string hash — reproducing the external SQLite table **inside the
weights**, worse and slower, and proving nothing about neural addressing. The paraphrase / unseen-entity
/ hard-name splits exist precisely to force **semantic** matching over symbolic hashing; this document
makes that a hard, mechanically-checked constraint rather than an implicit hope.

## 2. Prohibited constructions (each forbidden; each mechanically checked)

| # | prohibited shortcut | why forbidden |
|---|---|---|
| 1 | **Exact string matching** between query and stored key | reduces to symbolic hashing, not semantic matching |
| 2 | **Shared opaque IDs** (e.g. `supplier_142`) copied into both query and key | matching becomes ID equality, not identity understanding |
| 3 | **Shared canonical tokens** injected into both sides | same as #2 in disguise |
| 4 | **String hashing / dictionary equality** performing the lookup | not a learned representation |
| 5 | **Evaluator slot indices** as the matching target | oracle leakage |
| 6 | **Answer-derived keys** (the value appears in / determines the key) | encodes the answer into the address |
| 7 | **Future-query-aware writes** (write conditioned on the eventual question) | leaks the query into storage |
| 8 | **Fixed-class identity memorization** (closed-set softmax over known entities) | cannot generalize to unseen identities |
| 9 | **Train/eval entity overlap** enabling a lookup table | measures memorization, not mechanism |
| 10 | **Hidden external-table consultation** during E1 inference | E1 must not depend on the table |
| 11 | **Post-hoc key construction from the expected answer** | oracle leakage |

## 3. Legitimate key contract

The stored key **identifies the fact without containing its answer** and derives **only** from
information available at write time (entity description, attribute/relation description, write-event
context). The query is a natural-language question that **does not expose the literal stored-key token**.
Matching is over **learned embeddings** compared by the frozen cosine score, **episode-local**, and must
survive surface-form perturbation.

```
LEGITIMATE
  key   : "Northbridge Components — current supplier eligibility status"
  value : "suspended"
  query : "Can another purchase order be issued to Northbridge?"      # no literal key token, no "suspended"

FORBIDDEN
  key   : "supplier_142.status"
  query : "... supplier_142.status ..."                                # exact-symbol overlap -> shortcut
```

## 4. Mechanical tests the eventual harness must implement (before the reserved cohort)

Each test is a pass/fail gate on the **constructed data + trained-but-pre-reserved fixtures**, never on
reserved-seed outcomes.

1. **No prohibited exact-identifier overlap.** For every (query, correct stored key) pair, assert the
   overlap of normalized tokens contains **no** opaque/canonical identifier and **no** verbatim key
   token engineered to make the answer obvious. Report the overlap distribution; fail if any engineered
   identifier is shared.
2. **Unseen evaluation identities.** Assert the set of entity identities in every held-out split is
   **disjoint** from all training identities (splits G1–G6). Fail on any intersection.
3. **Unseen entity–value combinations.** Assert evaluation (entity, attribute, value) tuples do not
   appear in training (split G5). Fail on overlap.
4. **Surface-form perturbation preserves legitimate matching.** Under controlled paraphrase / casing /
   spacing / synonym perturbation of the query (G2), a legitimately semantic matcher should retain
   matching; a symbol-hash matcher would collapse. Report the perturbation sensitivity curve. (This is a
   **diagnostic** that distinguishes semantic from symbolic matching, not a reserved-seed selection.)
5. **Opaque-symbol relabeling cannot preserve success.** Randomly relabel any opaque symbols
   (consistently) and assert that a pure-symbol matcher's score is **unchanged** while the task
   semantics are unchanged — i.e., demonstrate that success **cannot** be achieved by symbol identity
   alone. Any arm whose accuracy is invariant to semantic content but sensitive only to symbol identity
   fails this test.
6. **No answer value in the stored key.** Assert the stored key string/embedding does not contain the
   value token or a deterministic function of it. Fail on any occurrence.
7. **No expected answer used to select or score the key.** Static + runtime assertion that key selection
   and scoring never read the target/label; the oracle-key path is diagnostic-only and flagged
   separately. Fail if the label is reachable from the selection path.
8. **No external-table access during E1 inference.** Assert the E1 inference path imports/invokes no
   ephemeral-table lookup. Fail on any table call in the ordinary inference path.

## 5. Split construction and leakage control (train / dev / final)

- **Identity partition:** entity identities are partitioned into disjoint train / development / final
  pools **before** any training; held-out splits draw identities only from the final pool.
- **Combination partition:** (entity, attribute, value) combinations for G5 are held out at the
  combination level, not merely the identity level.
- **Development fixtures** (for freezing thresholds, temperature, no-match sampling, etc.) use the
  development pool only. **Reserved final seeds/identities are never inspected before gates are frozen.**
- **Paraphrase generation** for G2 uses a frozen, preregistered transformation set; paraphrases of a
  final-pool identity stay in the final pool (no cross-contamination into train).
- **Determinism:** split construction is seeded and reproducible; the construction seed, ordering, and
  randomization rule are frozen (see gate/compute plan).

## 6. Outcome on any failure

If any §4 test fails, or any §2 construction is detected at build or run time, the experiment terminates
with `EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED` and the run is **not** counted as a capability result —
accuracy is irrelevant once integrity is breached. `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` and
`KDA_VALIDATION_BLOCKED` are preserved regardless.
