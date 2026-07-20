# RELATIONSHIP_BENCHMARK_AUDIT — Falsification Audit of the Resolution Layer

**Purpose:** determine whether the Relationship Resolution framework is a
trustworthy scientific instrument *before* it is used to evaluate future
resolvers. This is an audit, not a performance phase. SEEB v1.0.0, Hybrid
Handover, baseline extractors, retrieval benchmark, pipeline metrics, routing,
and validators are all unmodified (verified). Only one objective measurement bug
in the resolution framework was corrected (below). All corpora synthetic.

Run: `python -m agentic.hybrid_handover.resolution.audit.run_audit`

## Final verdict: **NOT READY TO FREEZE**

The framework's *headline* discovery metric (Relationship Edge Precision/Recall)
and its stage-attribution are sound, but several component metrics are gameable
or conflated, the deterministic resolvers pass by cue-vocabulary matching shared
with the gold, and governance has unspecified behaviour on structures outside the
16 cases. These must be corrected before the relationship benchmark can be frozen
and trusted to certify "relationship reasoning".

## Research questions — answered

**1. Can the benchmark be gamed?** Partially, yes. Trivial cheating resolvers max
several component metrics (see ADVERSARIAL_RESOLVERS.md):
- `always_abstain` scores **1.0** on `cycle_detection_accuracy`,
  `abstention_accuracy`, `coverage_abstention_accuracy` — while falsely abstaining
  on **11/11** non-abstain cases.
- `always_first/latest/override/allowed` score **1.0** on
  `definition_resolution_accuracy` and `exception_resolution_accuracy` — because
  those cases' expected *answers* do not depend on the definition/exception
  (they are distractors to the top-line answer).
- `negation_interpretation_accuracy` = **1.0** for any node-picker (it measures
  the shared answer-deriver, not relationship reasoning).
- `relationship_type_accuracy` = **1.0** for *every* cheat including `null`
  (it measures the shared parser, not the resolver).

**2. Does it reward authored graph knowledge?** Yes, methodologically. The
deterministic resolvers detect relationships by matching a fixed cue vocabulary
that is shared with the authored gold. Mirror cases (MIRROR_CASE_ANALYSIS.md)
show RuleResolver/GraphTraversalResolver detect **4/4 entity/order/number
mirrors** but only **1/4 wording mirrors** — a resolver that memorised SEEB's
exact cue phrases would score well without genuine understanding.

**3. Are metrics leaking ground truth?** No code leakage (LEAKAGE_ANALYSIS.md):
resolvers receive only `(question, evidence)`; signatures carry no case identity;
no resolver references `GOLD`/`case_id`. The only leakage is the methodological
cue-collusion in Q2.

**4. Can a trivial resolver score high without solving reasoning?** Yes on the
gameable metrics above; **no** on Relationship Edge Recall (0.00 for every cheat)
and on precedence/override/version/conflict resolution. End-to-end, trivial
"last-word-wins" resolvers reach 6/16 — the same as the weak FrozenResolver — so
6/16 is the trivial floor, and genuine graph reasoning is needed to reach 13/16.

**5. Does it separate discovery / classification / application / packet?**
Partially. Discovery (edge P/R) and classification (type accuracy) are separable,
but *application* (governance) and *packet construction* are entangled in the
outcome-based capability metrics: edge recall 0.94 co-exists with Precedence
Resolution 0.33 because the gap is packet construction, not discovery. A clean
governance-only metric is missing (recommended addition).

## Objective bug found and fixed
`allows_terminate("Neither party may terminate…")` returned `True` because
"n**either** party may terminate" contains "either party may terminate" as a
substring. This silently mislabelled negation clauses as permissive and made
FrozenResolver's graph always empty. Fixed with a word-boundary match. SEEB
resolution discrimination is unchanged (Frozen 6 / Rule 9 / Graph 13; Frozen edge
recall corrected 0.00 → 0.059).

## What must be corrected before freezing
1. **De-game the abstention-linked metrics.** `cycle_detection`, `abstention`,
   `coverage_abstention` are maxed by always-abstain. Add a **false-abstention
   rate** and require detection metrics to be conditioned on it (credit only
   resolvers that do not over-abstain).
2. **Fix distractor-based capability metrics.** `definition_resolution` and
   `exception_resolution` do not test their capability because the expected
   answer is independent of the definition/exception. Add graph-level metrics
   (is the `conflicts_with` / `exception_to` edge present and correct?) — do not
   rely on the outcome answer.
3. **Reclassify shared-stage metrics.** `negation_interpretation` and
   `relationship_type_accuracy` measure the shared deriver/parser, not the
   resolver. Label them as such; do not present them as relationship-reasoning
   evidence.
4. **Separate application from construction.** Add a governance-only accuracy
   (given the resolver's graph, is governing/abstain correct?) and a
   packet-construction accuracy (given correct governance, is the answer
   correct?). (Additions, not replacements.)
5. **Add wording-varied hidden cases.** The benchmark rewards cue-matching; a
   rotating, wording-varied hidden mirror set is required so cue-memorisation
   cannot certify reasoning.
6. **Specify governance on out-of-distribution structures.** Robustness
   (BENCHMARK_ROBUSTNESS.md) shows no relevance filter (irrelevant nodes pollute
   the governing set), silent ambiguity on parallel overrides, unmodelled nested
   exceptions, and attr-dependent dangling detection. Define these behaviours and
   make dangling detection structural (`dst ∉ nodes`).

## What is already sound (keep)
- Relationship Edge Precision/Recall — not gameable (0.00 for all cheats).
- Single-stage failure attribution — no double counting; localises the residual.
- Ground-truth graphs — structurally clean, no redundant/erroneous edges
  (GROUND_TRUTH_AUDIT.md).
- No code-level ground-truth leakage.
- Determinism — the entire audit is byte-reproducible.

## Scope caveat
This audit is on 16 synthetic cases with deterministic resolvers. It certifies
the *instrument*, not any resolver's real-world ability. The corrections above are
prerequisites for trusting the relationship benchmark; they are not
score-improvements and do not touch SEEB.
