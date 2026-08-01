# Story-Graph Layer — Structural Assembly, Not Event Counting

An additive layer over the sequence-risk analyzer that measures whether linked
events are **structurally assembling the same capability** as a known pattern —
not merely how many events resemble it. It reuses the existing linkage, ledger,
and purpose/providers machinery; the default `observe()` path is unchanged.

Modules: `storygraph.py` (engine), `storyverdict.py` (dual-story + completion),
`stories.py` (library), `financial.py` (account-takeover ontology),
`story_bridge.py` (runs a story against a live assembly). Advisory only.

## 1. Story graph, not a flat checklist

A pattern is a typed graph:

- **Nodes** — capability events (reuse the fragment vocabulary), one or more
  marked *completion* (the loss-producing action).
- **Edges** — typed constraints between *specific* node pairs. Full vocabulary
  (`storygraph.py`, schema `ctd.storygraph/1.0.0`): `ORDER`/`BEFORE`,
  `WITHIN`/`WITHIN_TIME`, `SAME_ENTITY(dim)` with aliases `SAME_ACCOUNT` /
  `SAME_DEVICE` / `SAME_BENEFICIARY` / `SAME_DESTINATION`, `RELATED_ACTOR(S)`,
  `REQUIRES_CORROBORATION`, `CONTRADICTS` (if both nodes present the harmful story
  is weakened → `contradicts_triggered`, category `AMBIGUOUS_COMPETING_STORIES`),
  and `COVERED_BY_AUTHORIZATION` (legit-graph coverage annotation). The matcher
  reports `satisfied_edges`, `failed_edges`, `contradicts_triggered`,
  `ordering_ambiguous`, `multiple_optimal_bindings`, and `unavailable`.

`evaluate_proposed_action` returns a single **structural vector** (§3) — node
coverage, ordering/entity/timing consistency, corroboration, completion proximity,
**trusted-context coverage**, and the typed **contradiction findings** — never one
fraud score. The harmful story graphs, verified legitimate stories, and the
storygraph schema are bound in the evaluation **freeze** (`evaluation/freeze.py`,
implementation-order item 11), so an official run refuses a changed StoryGraph.

This makes the discriminating relationships first-class, which a flat
required/optional set cannot express.

## 2. Deterministic bounded matching → a decomposed risk vector

Observed events are assigned to nodes to **maximize satisfied edges** (bounded,
sorted, deterministic — small graphs, capped combinations, greedy fallback marked
`bounded`). The result is a *vector*, not a count:

```
coverage · ordering_consistency · entity_consistency · timing_consistency
  · corroboration · proximity  →  harmful_score = frozen_weighted_sum
```

**Structural gates.** A threat-consistent verdict requires minimum
`entity_consistency` and `ordering_consistency` (and optionally `timing`). A
sequence with the right nouns but the wrong beneficiary/device or wrong order
trips the gate — its score is capped below the threat threshold, so it does **not**
escalate on coverage alone. Weights are human-set and frozen (no learning);
every dimension reports numerator/denominator and which edges failed.

Worked example (`cli story`): five account-takeover events with a **mismatched
beneficiary** → `coverage 1.0` but `entity_consistency 0.67` → gate → `OBSERVE`,
not `ESCALATE`. The same five with the matching beneficiary/device in order →
`ESCALATE`.

## 3. Dual-story evaluation

For each linked assembly two explanations are weighed:

- **Harmful story graph** → the risk vector above.
- **Legitimate counter-story** → a *verified* explanation from the trusted-provider
  / purpose layer (self-declared purpose never neutralizes). It can **partially**
  cover (steps 1–4 approved, the beneficiary in step 5 not) — a state the earlier
  subtractive model could not express.

A **contradiction** layer scores facts that weaken a story (approval covers a
different account, unauthorized destination, amount over cap, after approval
expiry, concealment behavior, unreliable linkage → ambiguous).

## 4. Comparative verdict taxonomy (advisory)

`NO_MATERIAL_PATTERN · PARTIAL_HARMFUL_MATCH · VERIFIED_LEGITIMATE ·
LEGITIMATE_PARTIALLY_COVERS · AMBIGUOUS_COMPETING ·
THREAT_CONSISTENT_WITHOUT_BENIGN · WOULD_COMPLETE_PROHIBITED ·
CONFIRMED_VIOLATION`. Each maps to the analyzer's advisory alphabet
(`OBSERVE`/`ESCALATE`); policy owns any binding consequence. It never asserts
intent — only structural consistency and whether verified context explains it.

## 5. Forward completion-gating (the strongest feature)

`would_complete(graph, events, proposed_action)` asks whether admitting an
individually-authorized pre-commit action would **complete** an already-assembled
harmful story whose completing step no verified counter-story covers. This is the
ActionGate integration: the per-action gate consults the sequence layer for a
completion signal on the exact proposed transition. In the demo, proposing the
transfer with the matching beneficiary/device → `WOULD_COMPLETE_PROHIBITED`;
with a different beneficiary → does not complete.

## 6. Determinism & limits

Deterministic (frozen weights, sorted iteration, no wall-clock/randomness);
stable `match_digest`/`verdict_digest`. Bounded matching degrades to a marked
greedy binding under size pressure. Known-pattern only — a genuinely novel pattern
matches nothing (an anomaly/graph-learning layer would be separate and advisory).
Positioned as **known-pattern sequence risk**, not intent inference.

## 7. Dual-story graph + per-node coverage (`legitimate.py`)

The legitimate explanation is its **own graph**, not a single status. A
`LegitimateStory` maps harmful-graph nodes to `CoverageRule`s that a **verified**
`Authorization` (from a trusted provider; `valid=True` only) must satisfy —
per-dimension entity match, time window, amount cap. Coverage is measured against
the **harmful** graph's nodes, so a recovery authorization that covers only the
reset and device enrollment yields `PARTIAL` coverage of an assembly that also
added a beneficiary and a transfer:

```
covered:   reset, device
uncovered: benef, xfer      → status PARTIAL, completion (xfer) not covered
```

Self-declared authorization (`valid=False`) covers nothing. Hard contradictions
remain non-compensatory — coverage never overrides them.

## 8. Typed contradictions (`contradictions.py`)

Explicit typed findings, each stating which graph it weakens (HARMFUL / LEGITIMATE
/ BOTH), the affected node/edge, evidence, and advisory-vs-decisive:
`APPROVAL_ACCOUNT_MISMATCH`, `APPROVAL_DESTINATION_MISMATCH`,
`APPROVAL_AMOUNT_EXCEEDED`, `APPROVAL_EXPIRED`, `ACTOR_SCOPE_MISMATCH`,
`DEVICE_BINDING_MISMATCH`, `BENEFICIARY_BINDING_MATCH`, `CONCEALMENT_EVENT_PRESENT`,
`ORDERING_AMBIGUOUS`, `ENTITY_LINKAGE_AMBIGUOUS`.

## 9. Minimal completion witness / deterministic certificate

`evaluate_proposed_action(assembly_events, proposed_action, harmful_graph,
legitimate_stories, authorizations, facts, now)` hypothetically inserts the
proposed action (never records it) and — when it completes the harmful graph —
returns a `CompletionWitness`: one event per required node, the proved binding
relations (same account/device/beneficiary, order, timing), a proof that removing
the proposed action makes the story incomplete (`removal_breaks_completion`,
`proposed_is_necessary`), and a `certificate_digest`. The canonical categories are
`NO_MATERIAL_PATTERN / PARTIAL_HARMFUL_STORY / VERIFIED_LEGITIMATE_STORY /
LEGITIMATE_STORY_PARTIAL_COVERAGE / AMBIGUOUS_COMPETING_STORIES /
THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT / WOULD_COMPLETE_PROHIBITED_CAPABILITY
/ HARD_POLICY_VIOLATION`, mapped to `OBSERVE`/`ESCALATE`/`UNAVAILABLE`.

## 10. Backward compatibility + matcher safety

`from_recipe()` compiles an existing flat recipe into a simple StoryGraph
(fragments → nodes, ordering → ORDER edges, gaps → WITHIN edges, relaxed entity
gate) so prior recipes keep working. The matcher reports `unavailable` (fail-
visible → `UNAVAILABLE` signal) when the binding-combination limit is exceeded,
plus `ordering_ambiguous` and `multiple_optimal_bindings`.

## Scope note

This is the first vertical slice: one harmful graph (account takeover) + its
verified counter-story. No large story library, no PageRank, no learned/
probabilistic scoring, no unknown-fraud discovery. Known-pattern sequence risk,
advisory only.

## Novelty

Subgraph attack-pattern matching, competing-hypothesis analysis, and fraud
story-graphs have substantial prior art. The differentiation is the *composition*
— deterministic, explainable dual-story graph assembly + typed contradictions +
forward completion-gating with a minimal witness, bound to ActionGate's
exact-action identity and verified non-compensatory context. Not an
established-novelty claim; patentability of the integrated completion-gating method
would require professional prior-art review.
