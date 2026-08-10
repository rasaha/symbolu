# Decision Authority — import graph (before)

## Kernel outbound (before)

`decision_governance` imports only: Python standard library + **pydantic**. It imports **no**
Ugence package (verified by AST scan; no `governance_providers`, `ugence_governance_contracts`,
`cer_v0_*`, or consuming-layer imports).

## Inbound consumers (who imports `decision_governance`)

Real consumers (excluding gitignored `build/` artifacts):

| Consumer | Files importing `decision_governance` |
|---|---:|
| `ai_hiring` | 75 |
| `domains` (hiring, procurement) | 18 |
| `governance_providers` | 6 |
| `packaging` (verifiers) | 4 |
| `enterprise_validation_pilot` | 4 |
| `comparative_governance_benchmark` | 3 |
| `applications` | 3 |
| `tap_provider` | 2 |
| `actiongate_provider` | 2 |
| `platform_freeze` | 1 |

Dependency direction: `applications → domains → decision_governance`; providers and pilots
consume `decision_governance.api`. The kernel is a leaf with respect to Ugence packages.
