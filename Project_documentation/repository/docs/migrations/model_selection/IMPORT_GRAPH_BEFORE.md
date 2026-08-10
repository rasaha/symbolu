# Model Selection — Import Graph (BEFORE)

At pre-migration tip `2a5a8efc`.

## Product core (outbound)

`execution_gate/{gate,policy,states,model,registry,reason_codes}.py` — imported only each other and the
Python standard library. No external dependency.

## Consumers (inbound → `execution_gate`)

```
control_plane/adapters.py                         → execution_gate.{gate,model,policy,registry,states}
control_plane_shadow/adapters/execution_gate_adapter.py → execution_gate
control_plane_shadow/adapters/model_policy_adapter.py   → model_selection_experiment.policy
execution_gate_shadow/*                           → execution_gate.{gate,model,states}
governed_inference_pilot/adapters/execution_gate.py → execution_gate.gate
execution_gate/{harness,baselines,scenarios}.py   → execution_gate.{gate,policy,registry,states,…}
```

## Sibling research (independent)

`model_selection_experiment`, `model_selection_pilot`, `model_selection_reconciliation` imported **no**
`execution_gate` — self-contained; `reconciliation → experiment` only.

## Shape

The product core was a stdlib-only leaf *inside* `execution_gate/`, but physically intermixed with that
directory's research harness (`harness`/`baselines`/`scenarios`) and its replay-freeze tree.
