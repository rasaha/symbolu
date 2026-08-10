# Decision Authority — artifact classification (§6)

Every Decision Authority-related artifact, classified and dispositioned. The bounded
domain-neutral kernel separates cleanly from applications and platform responsibilities
(gate **D2**).

| Artifact | Current path | Classification | Consumers | Target disposition | Evidence |
|---|---|---|---|---|---|
| Governance kernel (api/actions/decisions/audit/execution/identity/policy/ports/repositories/services/base/common/errors/vocabulary/surface/version) | `decision_governance/**` | CANONICAL_CAPABILITY_SOURCE | domains, ai_hiring, providers, pilots | **Move** → `ugence_decision_authority` | relative-only imports; pydantic+stdlib; 29 tests |
| Public API package | `decision_governance/api/**` | CANONICAL_PUBLIC_API | all consumers | **Move** (surface preserved) | freeze api hash `1b893869…` byte-identical |
| Conformance kit | `decision_governance/conformance/**` | CANONICAL_CAPABILITY_SOURCE | ai_hiring, domains | **Move**; kernel-prefix check accepts canonical name | domain conformance green after move |
| Kernel tests | `decision_governance/tests/**` | TEST_OR_FIXTURE | — | **Move** → package `tests/`; retarget/rewrite | 79 package tests pass |
| Legacy namespace (post-move) | `decision_governance/__init__.py` | COMPATIBILITY_LAYER | all legacy imports | **Create** logic-free shim | identity tests pass |
| Legacy distribution | `packaging/decision-governance/` | COMPATIBILITY_LAYER | dependency name `decision-governance` | **Repurpose** → depends on canonical wheel | pyproject shell |
| Freeze manifest / API snapshots | `platform/PLATFORM_FREEZE_V1.json`, `platform/api-snapshots/decision_governance.api.json` | FREEZE_OR_API_EVIDENCE | CI freeze | **Re-baseline** structural fields only | 2-field diff; snapshots byte-identical |
| `domains/hiring`, `domains/procurement` | `domains/**` | DOMAIN_EXTENSION | applications | **Out of scope** — consumer | imports kernel; not kernel |
| `ai_hiring` | `ai_hiring/**` | APPLICATION_LAYER | — | **Out of scope** — consumer | application on the kernel |
| `applications/**` | `applications/**` | APPLICATION_LAYER | — | **Out of scope** | product/domain composition |
| `governance_providers`, `tap_provider`, `actiongate_provider` | — | PROVIDER_IMPLEMENTATION | — | **Out of scope** | provider framework, separate migrations |
| ACP, StoryGraph, Agent Runtime, Model Selection, Hybrid LLM, LLM Steering | — | OUT_OF_SCOPE | — | **Out of scope** | separate capabilities |
| AI Control Plane, optional orchestrator, *Decide* product | — | OUT_OF_SCOPE | — | **Out of scope** | platform / product, not the bounded kernel |
| `ugence_governance_contracts` | `packages/governance-contracts/` | SHARED_GOVERNANCE_CONTRACT | providers | **Not a dependency** — kernel does not import it | AST scan: no import |

**Boundary verdict:** the domain-neutral Decision Authority kernel is separable from every
application, domain, provider, product, and platform responsibility. No file was moved merely
because it imports `decision_governance`.
