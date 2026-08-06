# Single-hop typed-vs-prose benchmark — shortcut & leakage analysis (DRAFT)

Companion to `SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md`. Documentation-only; nothing implemented or
executed. This analysis enumerates the ways a B1 (typed) win could be **spurious** and the mechanical guards
that the future experiment must implement before any run. The governing principle: **a representation
advantage is credited only if it is information-equivalent, causally load-bearing, and shortcut-free.**

## 1. The core threat: an unfair or leaky representation
The hypothesis compares *representations of identical facts*. The dominant risks are that B1 quietly carries
**more information**, an **easier surface**, or a **label shortcut** that B0 lacks — any of which would
manufacture a B1 win unrelated to "typed structure helps reasoning."

## 2. Threats and required guards
| # | Shortcut / leak | Why it fakes a B1 win | Mechanical guard (preregistered) |
|---|---|---|---|
| 1 | **Extra info in B1** (a typed field with no B0 counterpart) | B1 answers from info B0 never had | Information-equivalence verifier + shared canonical fact-set hash; fail closed on mismatch |
| 2 | **Answer label in a field name / value** (e.g. `correct_target:`) | B1 reads the answer | Ban answer labels/evaluator-only fields; scan field names + values against the target set |
| 3 | **Relation type encodes the answer** | relation string ≈ the label | Relation vocabulary frozen + checked to not be a function of the target |
| 4 | **Evaluator-only IDs** present in either arm | ID correlates with truth | Only authorized working-set IDs serialized; evaluator IDs stripped |
| 5 | **Fixed output-position shortcut** (answer always slot k) | positional guess wins | Randomize target position across candidates; report position-frequency baseline ≈ chance |
| 6 | **Unique token prefix reveals arm/answer** | trivial pattern match | Shared token space; no arm-identifying or answer-identifying prefixes; scan |
| 7 | **Train/final entity overlap** | memorization, not reasoning | Disjoint entity pools (train vs final); mechanical overlap check = 0 |
| 8 | **Train/final template overlap** creating trivial matching | template memorization | Disjoint / paraphrased templates where overlap would trivialize; report overlap |
| 9 | **B1-only access to authoritative answers** | direct leak | Ground truth never serialized into either input; targets used post-hoc only |
| 10 | **B0 serializer artifact correlated with the label** | prose surface leaks label | Serializer audited: surface features (order, punctuation, phrasing) independent of target; artifact-vs-label correlation ≈ 0 |
| 11 | **External-table lookup at inference** | answers from the table, not reasoning | No table access inside model inference (source scan) |
| 12 | **Post-hoc threshold / prompt / serializer change on final data** | overf_it to reserved cohort | Frozen serializer/schema/gates before final; source-hash lock; no final-driven edits |

## 3. Required near-chance baselines (both arms, final cohort)
Each must be at or near chance, or the split is a shortcut, not a reasoning test:
- **lexical-overlap** matcher (pick the candidate with most token overlap);
- **latest/first-record** heuristic (pick by position in the working set);
- **entity-frequency** heuristic (pick the most/least frequent entity);
- **relation-type frequency** heuristic;
- **evidence-position** heuristic (pick evidence by fixed slot).
If any baseline is materially above chance on a split, that split is quarantined and reported, and cannot
contribute a B1 advantage unless the elevation is identical across B0 and B1 (a task property, not a
representation shortcut).

## 4. Causal load-bearing requirement (not a leak guard, but the competence proof)
Even a clean, information-equivalent B1 win is credited as *reasoning* only if it **collapses** under the
causal ablations (§10 of the prereg): key permutation (A1), relation-target permutation (A2), relation
removal → abstention (A3), evidence permutation (A4). A B1 that stays high under A1/A2 is pattern-matching a
surface, not using the typed key/relation — reported as `…_CAUSAL_GATE_FAILED`, not an advantage.

## 5. Tenant-isolation guard
Cross-tenant substitution (A5) and cross-tenant decoys (S7) must yield **zero** unauthorized selection in
both arms. A typed representation that improves accuracy while leaking across tenants fails
(`…_TENANT_GATE_FAILED`) — isolation is a hard gate, not traded off against accuracy.

## 6. Symmetry principle (summary)
For every guard the question is the same: *would this feature give B1 an edge that is not "typed structure
helps reasoning over identical facts"?* If yes, it is removed, equalized across arms, or the result is
quarantined. Information-equivalence + causal collapse + shortcut baselines together make a validated B1
advantage attributable to representation, not leakage — which is the only claim the preregistration permits,
and only on controlled synthetic tasks.
