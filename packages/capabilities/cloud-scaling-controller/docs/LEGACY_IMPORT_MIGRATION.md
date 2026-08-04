# Legacy Import Migration

The scaling algorithm now lives in **one** canonical package:
`ugence_cloud_scaling_controller` (at
`packages/capabilities/cloud-scaling-controller/src`).

## Canonical vs legacy

| Old import | Status | New import |
|------------|--------|------------|
| `from cloud_controller.controller import Controller` | works (shim) | `from ugence_cloud_scaling_controller import Controller` |
| `from cloud_controller.config import InfraControllerConfig` | works (shim) | `from ugence_cloud_scaling_controller import InfraControllerConfig` |
| `from cloud_controller.core.coherence import CoherenceModel` | works (shim) | `from ugence_cloud_scaling_controller.core.coherence import CoherenceModel` |
| `from symbolu.cloud_controller.controller import Controller` | works (shim) | `from ugence_cloud_scaling_controller import Controller` |
| `import cloud_controller.replay.harness` | works (shim) | `import ugence_cloud_scaling_controller.replay.harness` |

## Guarantees during the compatibility period

- **Object identity is preserved.** `cloud_controller.controller.Controller`,
  `symbolu.cloud_controller.controller.Controller`, and
  `ugence_cloud_scaling_controller.controller.Controller` are the **same class
  object** — identical behavior, serialization, hashes, and errors.
- The legacy namespaces contain **no** scaling algorithm. `cloud_controller/` is a
  logic-free shim (a meta-path finder that routes each `cloud_controller.<sub>` to
  either the advisory package or the operations namespace — see below). The
  `symbolu.cloud_controller.*` chain resolves through the existing `symbolu`
  compatibility finder to the same objects.
- The stale nested duplicate `cloud_controller/cloud_controller/` and the dead
  physical copy `symbolu/cloud_controller/` were **removed**.

## Operational legacy imports (MONOREPO-ONLY)

As of 0.1.1, execution/operations code was moved OUT of the distribution into the
monorepo-only `cloud_scaling_operations` namespace. The following legacy operational
imports keep working **in the monorepo** and resolve there (object identity preserved):

| Old operational import | Resolves to (monorepo-only) |
|------------------------|------------------------------|
| `from cloud_controller.action.k8s_actuator import K8sActuator` | `cloud_scaling_operations.action.k8s_actuator` |
| `from cloud_controller.orchestrator import ProductionOrchestrator` | `cloud_scaling_operations.orchestrator` |
| `from symbolu.cloud_controller.action.k8s_actuator import K8sActuator` | `cloud_scaling_operations.action.k8s_actuator` |
| `from cloud_controller.recommend.engine import RecommendEngine` | `cloud_scaling_operations.recommend.engine` |

These operational imports are:

- **MONOREPO-ONLY** — they resolve only in a source checkout, never from a wheel.
- **NOT PART OF `ugence-cloud-scaling-controller`**.
- **NOT A STABLE DISTRIBUTED API** — subject to change/removal until separately
  packaged and governed (a future `ugence-cloud-scaling-operations`).

Advisory legacy imports (`cloud_controller.controller`, `.config`, `.core.*`,
`.signals.*`, `.shadow` readers, `.replay.*`, offline `.observability`,
`.recommend.confidence`/`.safety`, `.explain.*`) route to
`ugence_cloud_scaling_controller`.

## Scope of compatibility

The legacy namespaces are a **monorepo** compatibility surface. They are **not**
shipped in the wheel: an installed `ugence-cloud-scaling-controller` provides only
`ugence_cloud_scaling_controller` (no `cloud_controller`, no `symbolu`, no
`cloud_scaling_operations`). New and external code must import the canonical
namespace.

## Deprecation

The legacy shims are provided for a documented compatibility period and are intended
to be removed in a future major version. They are silent by design (no import-time
warning) so existing tests are unaffected; migrate at your convenience by switching
to `ugence_cloud_scaling_controller`.
