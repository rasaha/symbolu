# Migration

This document describes how policy packs reference downstream capabilities and
how legacy capability names map to the canonical names the compiler uses.

## Canonical capability names only

The compiler resolves capabilities exclusively by their **canonical** names, as
declared in the data-driven capability registry (`capability_registry.v1`, see
`CAPABILITY_REGISTRY.md`). Every capability has one canonical name; that name is
the stable identifier a pack should use.

## Legacy -> canonical mapping

Where older material refers to a capability by a product- or distribution-shaped
label, map it to the canonical registry name before compiling:

| Legacy / distribution label | Canonical capability name |
| --- | --- |
| `ugence-tap-provider` / `ugence_tap_provider` | `TAP` |
| `ugence-decision-authority` / `ugence_decision_authority` | `DECISION_AUTHORITY` |
| `ugence-actiongate-provider` / `ugence_actiongate_provider` | `ACTION_GATE` |
| `ugence-action-clearance` / `ugence_action_clearance` | `ACTION_CLEARANCE` |
| `ugence-storygraph` / `ugence_storygraph` | `STORYGRAPH` |
| `ugence-model-selection` / `ugence_model_selection` | `MODEL_SELECTION` |
| orchestration capability | `OPTIONAL_ORCHESTRATOR` |
| this package (structural) | `COMPILER` |

The distribution and namespace strings are recorded in the registry as metadata,
but a pack should refer to the capability by its **canonical name**, not by its
distribution name.

## Referencing capabilities by stable id

- A policy pack references a capability by its canonical registry name.
- The compiler uses **metadata only** to resolve the reference — it does not
  import the provider, and installation is not required to compile (see
  `CAPABILITY_REGISTRY.md`).
- A reference to a name not present in the registry raises the `UNKNOWN_CAPABILITY`
  validation rule (see `VALIDATION_MODEL.md`), so a mistyped or unmapped legacy
  label fails closed rather than resolving silently.

Because resolution is name-based and metadata-only, migrating a pack is a matter
of normalizing legacy labels to canonical names; no code, network access, or
installed provider is involved.
