# Model Selection — Import Graph (AFTER)

## Canonical package (outbound)

`ugence_model_selection/*` imports **only** the Python standard library and its own modules (verified:
zero non-stdlib, non-relative imports). A leaf.

## Inbound → `ugence_model_selection`

```
control_plane/adapters.py                          → ugence_model_selection.{gate,model,policy,registry,states}
governed_inference_pilot/adapters/execution_gate.py → ugence_model_selection.gate
execution_gate/__init__.py (compat shim)            → ugence_model_selection (aliases 6 core submodules)
execution_gate/tests/test_legacy_compat.py          → ugence_model_selection (+ execution_gate for identity)
scripts/model_selection_equivalence_capture.py      → execution_gate.* (→ canonical objects)
scripts/check_model_selection_single_impl.py        → (filesystem structural check)
```

## Inbound → `execution_gate` (compatibility surface, resolves to canonical objects)

```
control_plane_shadow/adapters/execution_gate_adapter.py → execution_gate
execution_gate_shadow/*                                 → execution_gate.{gate,model,states}
execution_gate/{harness,baselines,scenarios}.py         → execution_gate.{gate,policy,registry,states,…}
```

## Sibling research (unchanged; independent engines)

`model_selection_experiment`, `model_selection_pilot`, `model_selection_reconciliation` still import
**no** canonical or `execution_gate` code (`reconciliation → experiment` only). Their `__init__.py`
docstrings *reference* `ugence_model_selection` for classification but do not import it.

## Net change

The product core moved from *inside* `execution_gate/` to the canonical leaf package; every prior import
path still resolves (to the same objects) via the compatibility surface, and the two primary consumers
now depend on the canonical package by name. No cycle, no upward dependency, no inversion.
