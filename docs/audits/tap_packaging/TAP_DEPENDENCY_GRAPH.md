# TAP dependency graph

Machine-readable: `tap_dependency_graph.json` (AST over the canonical tree).

- **Edges:** 92 — `STDLIB` 37, `TAP_INTERNAL` (relative) 45,
  `UGENCE_GOVERNANCE_FRAMEWORK` 10.
- **External roots:** exactly one — `ugence_governance_provider_framework`
  (consumed only via its public `.api` surface).
- **`FORBIDDEN` edges:** 0 (no ActionGate, AI Hiring, applications, domains, kernel,
  research trees).

## Minimum hard-dependency decision

| candidate | verdict | rationale |
|---|---|---|
| `ugence-governance-provider-framework` | **CORE_HARD_DEPENDENCY** | TAP imports its `.api` during normal operation (10 edges). |
| `ugence-decision-authority` | **OPTIONAL_INTEGRATION_EXTRA** | 0 direct edges; reached only lazily through the framework's assessment-integration adapter → `decision-authority` extra. |
| `ugence-governance-contracts` | **TRANSITIVE_ONLY** | 0 direct edges; pulled transitively by the framework. |
| `decision-governance` / `dgm-provider-framework` (legacy) | **REMOVE_LEGACY_DEPENDENCY** | replaced by the canonical framework dependency. |
| ActionGate (`ugence-actiongate-provider` / `actiongate_provider`) | **excluded** | peer provider; 0 edges; not created in this PR. |

Final core dependency set: **`ugence-governance-provider-framework>=0.1.0`** only.
