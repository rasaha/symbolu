# ABLATION_DESIGN

How the labeler decides what a context span affects, and why the design does not
collapse everything into a single "P0" flag.

## Critical model

    F(C) = E            context C -> canonical ActionGate envelope E
    D(E, P, S) = Y      envelope + signed policy P + state S -> full decision record Y

For each semantic unit `u_i`:

    E_o = F(C)            ; Y_o = D(E_o, P, S)
    E_i = F(C \ u_i)      ; Y_i = D(E_i, P, S)

Both `F` and `D` are the **real** deterministic ActionGate path (see EXTRACTOR_SPEC
and `adapter.py`). A unit's effect is the diff `(E_o, Y_o)` vs `(E_i, Y_i)`.

## Effect taxonomy (multi-label — never merged)

| Label | Trigger |
|---|---|
| `NO_OBSERVED_EFFECT` | envelope and full decision record equivalent |
| `ENVELOPE_FIELD_CRITICAL` | a non-assurance envelope field changed (fields reported) |
| `DECISION_OUTCOME_CRITICAL` | the six-outcome disposition changed |
| `ASSURANCE_CRITICAL` | dispositive rules / applied constraints / reason changed, OR an assurance-input field (`credential_scope`, `state_freshness`, `reversibility`) changed |
| `REFERENCE_OR_STRUCTURE_CRITICAL` | a surviving unit references/depends on the removed unit |
| `EXTRACTOR_SENSITIVE` | oracle vs realistic extractor disagree on criticality — the change is attributable to F, not semantics |
| `REDUNDANT_CRITICAL_INFORMATION` | individually inert, but its redundancy set is critical |

A single removal may carry several labels. Collapsing them into one P0 bit is
exactly the diagnostic error this experiment avoids: "changed an amount" (envelope)
is not the same finding as "flipped DENY→ALLOW" (decision) or "dropped a required
approval" (assurance).

## Ablation modes

1. **Single-unit** — remove one unit; classify oracle effect; also classify the
   realistic-extractor effect to flag `EXTRACTOR_SENSITIVE`.
2. **Group** — remove a natural group (paragraph/section/table/turn-group).
3. **Redundancy-set** — remove all members of a `redundancy_set` together. Catches
   facts stated more than once that single ablation misses.
4. **Linked-pair** — remove preregistered relationship pairs (rule+exception,
   action+approval, claim+evidence, entity+alias, amount+currency,
   state+freshness, action+rollback).
5. **Limited interaction (DEV only)** — among individually-inert units, test pairs.
   **Frozen selection method:** sort inert unit ids, take the top
   `_INTERACTION_MAX_CANDIDATES = 6`, test unordered pairs up to
   `_INTERACTION_MAX_PAIRS = 15`. No exhaustive all-pairs, no Shapley. This method
   is fixed in `ablation.py` and is **not** run on the held-out split.

## Derived per-unit membership (for metrics)

- `decision/envelope/assurance/structure_units` — from single ablation.
- `redundant_units` — members of a critical redundancy set that were individually
  inert (so single ablation would have missed the fact).
- `interaction_units` — individually-inert units whose group/pair/interaction
  removal is critical.
- `interaction_only` (for the miss rate) — `(redundant ∪ interaction) − single_critical`.

The **critical union** counts each unit once even when multi-labelled, so
overlapping spans are never double-counted (tested).

## Why the oracle exists

The structured-oracle extractor establishes *true* semantic causality with zero
NLP error. The realistic extractor measures deployable behaviour. Any effect the
realistic extractor sees that the oracle does not (or vice versa) is labelled
`EXTRACTOR_SENSITIVE` and excluded from ground-truth critical sets — so extractor
noise is never mistaken for action-relevance.
