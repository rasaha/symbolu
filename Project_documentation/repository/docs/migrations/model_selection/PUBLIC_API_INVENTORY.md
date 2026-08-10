# Model Selection — Public API Inventory & Compatibility Classification

## Pre-migration snapshot procedure

`scripts/model_selection_api_snapshot.py` introspects the six `execution_gate` product-core submodules
— the surface established consumers import — and records every Model-Selection-owned public symbol with
its kind and signature/fields/members (stdlib re-exports like `dataclasses.field` are excluded so the
snapshot is deterministic). Captured in a pre-migration worktree (`api_before.json`) and in the migrated
tree via the compatibility surface (`api_after.json`).

| Snapshot | Symbols | sha256 |
|---|---|---|
| `api_before.json` | 51 | `3780087f866a7967…` |
| `api_after.json` | 51 | `3780087f866a7967…` |

**Byte-identical → compatibility classification: PATCH.** The consumer surface is unchanged.

## Consumer surface (stable, preserved)

| Module | Public symbols |
|---|---|
| `…reason_codes` | `ReasonCode` (enum, append-only), `normalize_raw` |
| `…states` | `EligibilityState`, `Verdict`, `Criticality`, `EvidenceSource`, `SOURCE_PRECEDENCE`, `Evidence`, `ConditionResult`, `EligibilityDecision` (+`to_dict`) |
| `…model` | `Request`, `Candidate`, `Signal`, `GateConfig` |
| `…gate` | `ExecutionGate` (+ names re-exported into its namespace: `Candidate`, `Request`, `Signal`, `Evidence`, `EvidenceSource`, `EligibilityState`, … — a deep-import surface `governed_inference_pilot` relies on) |
| `…policy` | `select`, `PolicyWeights`, `Selection` |
| `…registry` | `ExecutableRegistry`, `ModelRecord`, `ExecStatus` |

Available both as `execution_gate.<mod>` (compat, identical objects) and
`ugence_model_selection.<mod>` (canonical).

## New canonical public surface (additive)

`ugence_model_selection.api` re-exports the above (25 curated names in `__all__`) grouped by stage, plus
`fingerprint`, `POLICY_VERSION`, `VERSION`, `__version__`. `api.py` adds **no logic** and does not widen
the behavioral surface — it is a curated, grouped presentation of the same objects. `POLICY_VERSION`
preserves the legacy `"exec_gate_v1"` stamp so serialized decision records are unchanged.

## Serialization-sensitive elements (unchanged)

`EligibilityDecision.to_dict()` output, `ReasonCode` values (append-only), the enum values of
`EligibilityState`/`Verdict`/`Criticality`/`EvidenceSource`/`ExecStatus`, and dataclass field layouts —
all byte-identical (proven by both the API snapshot and the equivalence capture).
