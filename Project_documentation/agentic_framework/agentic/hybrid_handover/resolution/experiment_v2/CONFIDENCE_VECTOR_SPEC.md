# CONFIDENCE_VECTOR_SPEC — Proposal Validation Experiment v0.1

Edge confidence is an explicit, deterministic, **decomposable vector**. It is never
invented as a probability and never collapsed into one opaque score. Decisions read
the individual components, so every rejection is explainable by a named component.

## The four components

```
confidence_vector = { lexical, structural, authority, reference }
```

| component | domain | meaning | source |
|---|---|---|---|
| `lexical` | [0,1] | strength of the surface cue that triggered the proposal | v0.1 per-edge cue confidence (0.6–0.9) |
| `structural` | {0.0, 0.5, 1.0} | does the destination exist as evidence | 1.0 real node · 0.5 named-but-unresolved reference/alias · 0.0 dangling |
| `authority` | {0.0, 1.0} | is the edge direction order/temporal-consistent | 1.0 consistent or order-agnostic type · 0.0 ordering violated |
| `reference` | {0.0, 0.5, 1.0} | does a named reference/alias destination resolve | 1.0 resolves · 0.5 named-dangling · 1.0 n/a for non-reference types · 0.0 unfounded |

## Determinism
Each component is a pure function of parsed structure. There is no model, no
sampling, and no fitting: identical inputs yield an identical vector, and two full
experiment repetitions are byte-identical.

## How decisions use the vector (no collapse)
- `structural < 0.5` on a destination-required type → reject (`missing_destination_evidence`).
- `reference < 0.5` → reject (`unsupported_wording`).
- `authority == 0.0` → reject (`authority_mismatch` / `temporal_mismatch`).
- `lexical < FLOOR_LEXICAL (0.6)` → reject (`low_evidence`).
Type-specific and exclusivity gates (see the rulebook) are structural predicates
evaluated alongside the vector, not blended into it.

## Why decomposition matters here
A single blended score would hide *why* an edge was kept or dropped. Keeping the four
components separate lets the rejection analysis attribute each removed edge to a
concrete deficiency (no destination, wrong direction, weak cue, unresolved
reference), which is exactly what a precision-recovery study needs to report.

## Reported form
For every proposed edge the experiment records the full vector alongside the
decision and (if rejected) the category — see EDGE_REJECTION_ANALYSIS.md and the
per-edge records in `VALIDATION_RESULTS.json`.
