# Bounded Binding-Slot — Implementation Selection

**Date:** 2026-08-03 · **Source commit:** `8b4ec6e7` · Machine-readable twin:
[`slot_implementation_selection.json`](slot_implementation_selection.json)

All bounded-slot implementations in the repository were compared on the eight selection
criteria (measured result; causal slots-off evidence; bounded state; no N×N; no required Phase
dependency; clean source/version semantics; reproducible harness; minimal controller coupling).
Not chosen by class name, file date, or documentation language.

## Candidates

| | `BindingSlots` (phase_lc) | `BoundedBindingSlots` (lightweight) | `SlotMemoryGCT` |
|---|---|---|---|
| Path | `experiments/phase_lc/models.py:200` | `symbolu/lightweight_phase/binding_slots.py:63` | `symbolu/phase_transformer.py:8458` |
| Measured positive result | **yes** (`results/abc.json`) | no (validation deferred) | no |
| Causal slots-off + rand-address hooks | **yes** (`zero`/`rand_keys`) | no | no |
| Bounded state / no N×N | yes / yes | yes / yes | yes / yes |
| Requires Phase | no | no | no (but coupled to GCT controller) |
| source/version/supersession | no | **yes** | no |
| Reproducible harness | **yes** (`harness_abc.py`) | no | no |
| Controller coupling | minimal | minimal | heavy (GCT) |

`SlotMemoryGCT` is rejected: soft-EMA only, no metadata, and heavy GCT-controller coupling
(component disposition: REIMPLEMENT-if-retained).

## Decision

- **Primary reproduction target: `BindingSlots` (phase_lc).** It produced the only measured
  positive slot result and carries the exact ablation hooks the harness used; criteria 1, 2, 7
  are decisive for a *reproduction* phase. Incubated verbatim (class body byte-identical) as
  `src/binding_slots/legacy_phase_lc_slots.py`, Phase-free.
- **Metadata-extension reference: `BoundedBindingSlots` (lightweight).** The only implementation
  with source/version/supersession/eviction — the target for the not-yet-demonstrated
  relational capabilities. Incubated as `src/binding_slots/bounded_binding_slots.py` (body
  byte-identical; one import repointed). Its validation was deferred upstream, so it is a
  *variant to develop*, not the reproduction target.
- **Runnable stdlib reference: `slot_reference.py`.** Implements the union of testable discrete
  mechanics so behavioural/complexity claims run **without PyTorch**, and serves as the parity
  oracle for both torch modules.

This dual selection is deliberate: the phase_lc module is what we must *reproduce*; the
lightweight module is what we must *grow into* for relational memory; the stdlib reference is
what we can *test today*.
