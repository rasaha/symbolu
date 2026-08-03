# Capability Registry

The capability registry (`compiler/capability_registry.py`) is the data-driven
catalog of downstream capabilities the compiler can reference. Its version is
`capability_registry.v1`. The registry describes capabilities by metadata only;
it never imports or invokes a provider.

## Registry entries

| Capability | Distribution / namespace | Disposition | Optional | Version |
| --- | --- | --- | --- | --- |
| `TAP` | `ugence-tap-provider` / `ugence_tap_provider` | advisory | yes | 0.1.0 |
| `DECISION_AUTHORITY` | `ugence-decision-authority` / `ugence_decision_authority` | authoritative | **no** | 1.0.0 |
| `ACTION_GATE` | `ugence-actiongate-provider` / `ugence_actiongate_provider` | authoritative | yes | 0.1.0 |
| `ACTION_CLEARANCE` | `ugence-action-clearance` / `ugence_action_clearance` | authoritative | yes | 0.1.0 |
| `STORYGRAPH` | `ugence-storygraph` / `ugence_storygraph` | advisory | yes | 2.0.0 |
| `MODEL_SELECTION` | `ugence-model-selection` / `ugence_model_selection` | advisory | yes | 0.1.0 |
| `OPTIONAL_ORCHESTRATOR` | orchestration capability | — | — | — |
| `COMPILER` | this package (structural) | — | — | — |

`DECISION_AUTHORITY` is the only non-optional capability: a governed workflow
that decides must bind the decision to it. `COMPILER` is a structural entry
representing this tooling itself.

## Metadata-only resolution

Core compilation uses **metadata only**. The registry supplies distribution
name, namespace, disposition, optionality, and version so that synthesis and the
authority-boundary checks can reason about capabilities without any capability
being present on the machine. Compilation of a pack does not require any provider
to be installed.

## The optional installation probe

The registry offers an optional `is_installed` probe that uses `find_spec` to
report whether a provider distribution is importable. This probe:

- is **optional** — it is not part of core compilation, and
- **never imports** the provider — it only checks for the module spec.

This keeps compilation deterministic and side-effect free: whether or not a
provider happens to be installed, the compiled logical result is identical.

Referencing a capability that is not in the registry raises the
`UNKNOWN_CAPABILITY` validation rule (see `VALIDATION_MODEL.md`), and every
capability's declared disposition is enforced by the authority-boundary table
(see `AUTHORITY_BOUNDARIES.md`).
