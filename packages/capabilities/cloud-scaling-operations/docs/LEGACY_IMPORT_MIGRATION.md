# Legacy Import Migration

The operations implementation now lives in one canonical package:
`ugence_cloud_scaling_operations`.

Monorepo-only compatibility surfaces (object identity preserved) route to it:

| Legacy import | Resolves to |
|---------------|-------------|
| `cloud_scaling_operations.*` | `ugence_cloud_scaling_operations.*` |
| `cloud_controller.action.*`, `.orchestrator`, `.main`, `.recommend.{engine,approval,webhook}` | `ugence_cloud_scaling_operations.*` |
| `symbolu.cloud_controller.action.*`, `.orchestrator` | `ugence_cloud_scaling_operations.*` |

These legacy namespaces are **monorepo-only** and are **not a stable distributed
API**. A clean wheel install exposes only `ugence_cloud_scaling_operations`. Advisory
imports (`cloud_controller.controller`, etc.) continue to route to
`ugence_cloud_scaling_controller`.
