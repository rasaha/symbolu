# Source Inventory — Agent Workforce Composer P1

Package: `packages/capabilities/agent-workforce-composer` ·
Distribution `ugence-agent-workforce-composer` · Namespace
`ugence_agent_workforce_composer` · Version `0.1.0` · Contract `awc.v1`.

## Modules (`src/ugence_agent_workforce_composer/`)
| Module | Responsibility |
|---|---|
| `canonical.py` | frozen base model, canonical JSON, `sha256:` digests |
| `contracts.py` | neutral enum mirrors of the compiler vocabulary; `NodeDisposition`, `EvidenceClass`, `EligibilityState` |
| `reasons.py` | append-only `EliminationReason` taxonomy + `normalize_reason` |
| `fingerprint.py` | content-address helpers (`fingerprint`, `stamp_fingerprint`) |
| `workflow.py` | `WorkflowRoleRequirement`, `NonAgentDisposition`, `CompilerAdaptationResult` |
| `adapter.py` | `CompilerWorkflowAdapter` / `adapt_compiled_workflow`, node classification |
| `agents.py` | `AgentProfile`, evidence objects, `AgentRegistrySnapshot` |
| `policy.py` | `EnterpriseAgentPolicy`, `EligibilityPolicy` |
| `eligibility.py` | hard-constraint engine + results, explanation, replay |
| `fixtures.py` | synthetic procurement/support/security workflows, registry, policies, demos |
| `api.py` | curated public surface (48 names) |
| `cli.py` | offline CLI |
| `version.py` | versions + honest maturity metadata |

Total: ~2,884 source lines · **48** public API names · **84** tests.

## Supporting artifacts
`artifacts/public_api.json` (frozen API), `scripts/public_api_snapshot.py`,
`verify_agent_workforce_composer_distribution.py`, `conftest.py`, `pyproject.toml`,
13 docs, `.github/workflows/agent-workforce-composer-p1-ci.yml`.
