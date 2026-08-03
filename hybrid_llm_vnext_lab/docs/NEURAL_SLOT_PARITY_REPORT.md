# Neural Slot Parity Report

**Date:** 2026-08-03 · Test: [`../tests/parity/test_legacy_neural_slot_parity.py`](../tests/parity/test_legacy_neural_slot_parity.py) · Data: [`../artifacts/neural_slot_parity.json`](../artifacts/neural_slot_parity.json)

## Classification: `EXACT_PARITY`

The incubated neural slot class
`hybrid_llm_vnext_lab/src/binding_slots/legacy_phase_lc_slots.py::BindingSlots` is **numerically
identical** to the historical `experiments/phase_lc/models.py::BindingSlots`. This is the neural
parity that gates historical reproduction; it is **distinct** from the stdlib semantic reference,
which is **not** used as proof of neural parity.

## Measured (torch 2.13.0, CPU fp32)

| Comparison | Grid | Max abs error |
|---|---|---|
| Forward output | B∈{1,2} × N∈{1,8,32,160} | **0.0** |
| Input gradient | same | **0.0** |
| Parameter gradients | same | 0.0 |
| Ablation outputs | `None`, `zero`, `shuffle_val`, `rand_keys` | **0.0** |
| Diagnostics (`slot_util_entropy`, …) | — | ≤ 1e-6 |
| `state_dict` | keys + shapes | identical |

Construction: both modules seeded identically, then the incubated module loads the historical
module's `state_dict`; stochastic ablations reset the **same** torch seed immediately before each
forward so the random permutations/addresses match. Error is exactly **0.0** because the class body
is byte-identical (see provenance) — so with identical weights the outputs are bit-identical.

## Consequence

- **Incubated extracted neural class maturity: `NUMERICAL_PARITY`** (in fact EXACT). Historical
  reproduction is authorized to proceed against it.
- Any historical A/B/C reproduction that uses the incubated slot is therefore exercising the exact
  historical slot mathematics; the incubated Phase-free S-arm uses the same validated slot.

## Not parity

The **streaming** `BoundedBindingSlots` (dynamic keys, discrete threshold allocation, version/source
metadata) is a **RELATED_BUT_DIFFERENT_ALGORITHM** from the historical parallel-scan `BindingSlots`
(soft cumulative writes to fixed slots). No numerical parity is claimed between them; see
`../artifacts/neural_complexity_probe.json` and the streaming/decode notes.
