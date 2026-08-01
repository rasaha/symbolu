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
- **Edges** — typed constraints between *specific* node pairs: `ORDER(before→after)`,
  `SAME_ENTITY(dim)` (e.g. the transfer beneficiary must equal the added
  beneficiary; the transfer device must equal the registered device),
  `WITHIN(Δt)`, `RELATED_ACTORS`, `REQUIRES_CORROBORATION`.

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

## Novelty

Subgraph attack-pattern matching, competing-hypothesis analysis, and fraud
story-graphs have substantial prior art. The differentiation is the *composition*
— deterministic, explainable dual-story graph assembly + contradiction scoring +
forward completion-gating bound to ActionGate's exact-action identity and verified
non-compensatory context. Not an established-novelty claim; patentability of the
integrated completion-gating method would require professional prior-art review.
