# demo_data/

Input fixtures for the four Governance Studio demo scenarios, in the **real AWC
schemas** (`workflow_ir.v1` documents, `AgentRegistrySnapshot`, and the six
governance policies). Ten files per scenario:

| File | AWC schema |
|---|---|
| `compiled_workflow.json` | serialized `workflow_ir.v1` document |
| `enterprise_role_overlay.json` | overlay mapping (`node_id → field → value`) |
| `agent_registry_snapshot.json` | `AgentRegistrySnapshot` |
| `enterprise_agent_policy.json` | `EnterpriseAgentPolicy` |
| `eligibility_policy.json` | `EligibilityPolicy` |
| `ranking_policy.json` | `AgentRankingPolicy` |
| `composition_policy.json` | `TeamCompositionPolicy` |
| `permission_policy.json` | `PermissionBoundingPolicy` |
| `fallback_policy.json` | `AgentFallbackPolicy` |
| `scenario_manifest.json` | studio metadata + expected digests/fingerprints |

All fixtures are synthetic. Regenerate with
`python ../scripts/generate_fixtures.py`.
