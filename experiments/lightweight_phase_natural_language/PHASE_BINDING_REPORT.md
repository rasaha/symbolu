# Phase + Binding Validation — Report (v1.7)

**Question B:** Do bounded binding slots improve precise relational retrieval
beyond Phase alone? Measured by **C − B**.
**Question C:** Does Phase remain useful after binding slots are present?
Measured by **C − C-no-Phase**.

> Populated from `results/aggregate.json`, `results/ablations.json`,
> `results/resources.json`. Sections: implemented / tested / demonstrated /
> unsupported / deferred.

## Implemented
- Bounded binding slots (frozen `BoundedBindingSlots`) as a third additive path
  in C and C-no-Phase; O(M·D) streaming state; no `[B,N,M,D]` / N×N materialization.
- Slot ablations (disable, randomize keys, shuffle values, reduce Top-K).
- Capacity considerations (slots=16, top_k=4); binding stress (entities/facts).

## (results filled post-run)
