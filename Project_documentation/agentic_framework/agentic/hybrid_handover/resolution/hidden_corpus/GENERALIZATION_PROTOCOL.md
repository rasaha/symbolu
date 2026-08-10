# GENERALIZATION_PROTOCOL

How the hidden corpus is used to test relationship generalisation — and the
process discipline that keeps it honest.

## Protocol
1. **Never tune on hidden data.** Resolvers are developed only against the visible
   development corpus. The hidden corpus is run at most as a final measurement.
2. **Metadata-blind execution.** A resolver receives only `evidence_for(id)` /
   `executable_cases()`. Difficulty, capability, gold graph, and expectation are
   never passed in.
3. **Measure with the frozen Relationship Measurement Spec v1.0.** Score discovery,
   classification, governance (Mode G), packet (Mode P), and abstention decision
   metrics — the owner-clean set.
4. **Report public vs hidden together.** A large visible-minus-hidden gap is
   evidence of cue-memorisation and must be reported alongside any headline claim.
5. **Stratify by depth and capability.** Report per-Level and per-capability so
   shallow matching (good at Level 1–2, collapsing at Level 4–5) is visible.
6. **Rotate.** Expand and periodically rotate hidden cases so a resolver cannot be
   iteratively fitted to them across releases.
7. **No leakage regressions.** `leakage.verify()` must stay clean in CI.

## What a PASS would require (not claimed here)
A future resolver could be said to *generalise* only if, on the hidden corpus, it
sustains high owner-clean metrics across capabilities and depths, with a small
visible-minus-hidden gap — on a corpus large and dense enough that per-capability
scores are statistically meaningful. That corpus does not yet exist (see below).

---

## FINAL ASSESSMENT (conservative; no resolver performance reported)

### 1. Does the hidden corpus adequately measure relationship generalisation?
**Not yet — it is a sound seed, not a certification set.** Breadth is complete
(all 24 capabilities, all 9 edge types, difficulty 1–5, 5 negative controls, 11/13
variation dimensions, leakage-clean, integrity-clean). But **depth is shallow**:
13 of 24 capabilities have a single example, several edge types and all negative
controls are single-example, and two variation dimensions are absent. A single
example per capability can be satisfied by a bespoke rule, so the corpus can
currently *detect* gross cue-memorisation but cannot *certify* generalisation.

### 2. Which capabilities remain underrepresented?
Every single-example capability: `partial_overrides`, `table_vs_text`,
`appendix_precedence`, `entity_renaming`, `parallel_overrides`,
`conditional_applicability`, `multi_hop`, `nested_exceptions`, and all five
negative controls. Also thin: `version_supersession`, `scoped_exceptions`,
`effective_date_precedence`, `cross_document_reference`, `implicit_references`,
`hierarchical_governance`, `policy_migration` (2 each).

### 3. Which reasoning patterns still require additional cases?
- Deep multi-constraint composition (Level 5): only 2 cases.
- Parallel/conflicting authorities that DISAGREE with a required tie-break rule.
- Nested and conditional exceptions beyond depth 2.
- Multi-hop reference chains longer than 3 and with mixed implicit/explicit links.
- Proper-uncertainty variety: multiple distinct instances of each abstention type.
- Variation gaps: `sentence_structure` (passive/nominalised) and `clause_numbering`
  (inconsistent numbering schemes) are uncovered.

### 4. Minimum corpus size before claiming broad relationship generalisation
**Conservatively, on the order of several hundred hidden cases** — a defensible
floor is **≈5–10 varied cases per capability per difficulty band**. With 20
positive capabilities × ~3 relevant difficulty bands × ~5–10 cases ≈ **300–600
cases**, plus ≥5 varied instances for each of the 5 negative-control types and
each variation dimension. This seed (22 cases) is roughly **4–7%** of that floor.
Until that density exists, per-capability hidden scores are indicative, not
certifying.

### Bottom line
The hidden corpus establishes the *structure* a durable relationship benchmark
needs — hard executable/annotation separation, leakage-free opaque ids, depth-
graded difficulty, negative controls, and named blind spots — and provides a
validated seed. It is **not** yet large or dense enough to certify broad
generalisation, and this document states exactly what expansion that would require.
No claim is made about any resolver's ability, and no benchmark score was changed.
