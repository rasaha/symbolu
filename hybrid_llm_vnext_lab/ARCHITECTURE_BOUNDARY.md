# Hybrid LLM vNext Lab — Architecture Boundary

This file defines what may and may not cross into the incubation root.

## Allowed inside `src/`
- The selected bounded binding-slot implementation(s) (byte-identical copies with provenance).
- A dependency-free stdlib reference of the slot mechanics (`slot_reference.py`).
- A minimal local/window baseline needed to exercise slots.
- Neutral `Protocol` contracts (`SequenceMixer`, `RecurrentState`, `AuxiliaryMemory`).
- Instrumentation (bounded-state, no-N×N declarative audit, utilization, collisions,
  source/version retention).

## Forbidden inside `src/` (enforced by `tests/boundaries/`)
- Any Phase code or import: `PhaseAttentionLayer`, `HybridPhaseTransformer`,
  `BindingCachePhaseState`, `BindingCacheTransformer`, `symbolu.phase_transformer`.
- KDA / MLA implementation (this phase is slots-only; KDA is a later, separate phase).
- Ontological layers, governance code, Agent Runtime, ActionGate, routing, renderers,
  handover systems, GCT controllers.
- Investor/marketing documentation.
- Packaging metadata: `pyproject.toml`, wheel/sdist build, distribution config, entry points,
  consumer migration shims.

## Neutral-contract intent (prepared, not wired)
The slot subsystem is an **auxiliary memory** that must attach to *any* backbone without
depending on it:

```
AuxiliaryMemory: init_state() -> update(state, x, ...) -> read(state, q) -> readout
```

so the same slots can later sit beside:
- the local-window baseline in this lab,
- a future KDA recurrent backbone,
- a future KDA + periodic-MLA hybrid,
- a conventional attention baseline.

Slots must never import or subclass a specific backbone. The KDA/MLA backbone will be built in
a **separate** phase and composed through these contracts — never by editing the slot core.

## Original code is untouched
Everything here is a **copy**. The original implementations
(`experiments/phase_lc/models.py`, `symbolu/lightweight_phase/binding_slots.py`, their
harnesses and experiments) remain the historical reference and are **not moved, edited, or
repointed**. Provenance headers on every copied file record the exact source path, commit, and
git blob hash.
