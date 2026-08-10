# Model Selection — Consumer Map

Every consumer of the Model Selection product core, its import posture after the migration, and its
test result.

| Consumer | Posture after migration | Imports | Tests |
|---|---|---|---|
| `control_plane/adapters.py` | **Repointed to canonical** | `ugence_model_selection.{gate,model,policy,registry,states}` | `control_plane` 65 passed |
| `governed_inference_pilot/adapters/execution_gate.py` | **Repointed to canonical** | `ugence_model_selection.gate` | `governed_inference_pilot` 27 passed |
| `governed_inference_pilot/adapters/model_policy.py` | Unchanged (pilot selection variant) | its own `argmin cost s.t. quality≥q_min` | (in the 27 above) |
| `execution_gate_shadow/*` | **Legacy surface (compat)** | `execution_gate.{gate,model,states}` → canonical objects | in `execution_gate_shadow`+`control_plane_shadow` 81 passed |
| `control_plane_shadow/adapters/execution_gate_adapter.py` | **Legacy surface (compat)** | `execution_gate` | (in the 81 above) |
| `control_plane_shadow/adapters/model_policy_adapter.py` | Unchanged | `model_selection_experiment.policy` (research engine) | (in the 81 above) |
| `execution_gate/{harness,baselines,scenarios}.py` | Local research; consume canonical via aliases | `execution_gate.{gate,policy,registry,states,…}` → canonical | `execution_gate` 25 passed |

## Authority discipline preserved

- **Control plane** invokes Model Selection, supplies approved candidates and policy inputs, and
  receives the selected candidate or no-eligible result. It does not make an ineligible candidate
  eligible, alter the selection silently, execute the selected model, or become Model Selection's owner.
  `control_plane_shadow`'s adapter still intersects any selection with the eligible set and emits
  `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` rather than override.
- **Governed-inference pilot** still performs provider execution *after* selection; that execution
  remains outside the canonical package. The distinction *Model Selection chooses within policy →
  routing dispatches → provider execution invokes* is intact.

## Why two postures

Repointing the primary product/control-plane consumers demonstrates real dependency on the canonical
package; keeping the shadow harnesses on the `execution_gate` surface keeps the compatibility path in
active, tested use (`execution_gate/tests/test_legacy_compat.py` proves identity). Both resolve to the
same canonical objects, so behavior is identical either way.
