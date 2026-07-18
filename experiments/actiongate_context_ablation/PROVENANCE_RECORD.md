# PROVENANCE_RECORD

> **This study uses public (repository-derived) and authored naturalistic data, NOT confidential customer operational data.** No item can emit REAL_CUSTOMER_VALIDATED.

Manifest hash: `sha256:d0cde387dc40a6b8a56d9c1afae2de729e513c5af785dc8c0d3b19141a448b4b`  ·  77 contexts, 11 domains, 16 action types.

## Coverage

- **by_partition**: AUTHORED_REALISTIC_CORPUS=35, PUBLIC_NATURALISTIC_CORPUS=42
- **by_split**: DEV=28, HELDOUT_TEST=26, VALIDATION=23
- **by_structure_family**: prose=54, prose_tables=10, structured=13

## A. PUBLIC_NATURALISTIC_CORPUS — repository sources

| repo source | title | license | # items | action types |
|---|---|---|---|---|
| `.github/workflows/backbone-ci.yml` | backbone CI workflow | repo-internal (rasaha/symbolu) | 3 | branch_protection |
| `.github/workflows/pipeline-ci.yml` | pipeline CI workflow | repo-internal (rasaha/symbolu) | 3 | release_promotion |
| `cyber_security/action_gate_reference/action_gate_ref/policy.py` | policy R1 IAM_GRANT_ADMIN ruleset | repo-internal (rasaha/symbolu) | 3 | iam_grant |
| `cyber_security/action_gate_reference/action_gate_ref/policy.py` | policy R3 DB_DELETE ruleset | repo-internal (rasaha/symbolu) | 3 | cloud_storage_delete |
| `cyber_security/action_gate_reference/action_gate_ref/policy.py` | policy R5 SECRET_READ (export) | repo-internal (rasaha/symbolu) | 3 | customer_data_export |
| `cyber_security/action_gate_reference/action_gate_ref/policy.py` | policy R5 SECRET_READ ruleset | repo-internal (rasaha/symbolu) | 3 | secret_export |
| `cyber_security/action_gate_reference/action_gate_ref/policy.py` | policy R6 MONITORING_DISABLE ruleset | repo-internal (rasaha/symbolu) | 3 | monitoring_disable |
| `cyber_security/action_gateway/demos/scenarios.py` | gateway DB mutation scenario | repo-internal (rasaha/symbolu) | 3 | database_migration |
| `cyber_security/action_gateway/demos/scenarios.py` | gateway terraform apply scenario | repo-internal (rasaha/symbolu) | 3 | terraform_apply |
| `cyber_security/action_gateway_k8s/demos/scenarios.py` | k8s gateway delete enforcement scenario | repo-internal (rasaha/symbolu) | 3 | kubernetes_delete |
| `cyber_security/action_gateway_mcp/action_gateway_mcp/registry.py` | MCP tool registry credential scope | repo-internal (rasaha/symbolu) | 3 | credential_scope_change |
| `deploy/gke/deployment.yaml` | GKE Deployment manifest (rollback path) | repo-internal (rasaha/symbolu) | 3 | service_rollback |
| `deploy/gke/deployment.yaml` | GKE demo Deployment manifest | repo-internal (rasaha/symbolu) | 3 | kubernetes_deploy |
| `deploy/gke/rbac.yaml` | GKE RBAC / network exposure manifest | repo-internal (rasaha/symbolu) | 3 | network_policy |

Every public item records adapted=true with the exact adaptation (transforming a manifest / policy rule / demo scenario into an ActionGate request context; field names and short structural excerpts only). Per-item detail: `corpus/manifest.json`.

## B. AUTHORED_REALISTIC_CORPUS — authored scenario families

| domain | action types | # items |
|---|---|---|
| cicd | release_promotion, service_rollback | 4 |
| database | database_migration | 3 |
| iam | credential_scope_change, iam_grant | 5 |
| kubernetes | kubernetes_delete, kubernetes_deploy | 5 |
| monitoring | incident_mitigation, monitoring_disable | 4 |
| network | network_policy | 3 |
| payments | payment_refund | 3 |
| secrets | secret_export | 3 |
| storage | cloud_storage_delete | 2 |
| terraform | terraform_apply | 3 |

Authored items record license=original-authored, adapted=false — independently authored realistic scenarios, not harvested and not customer data.

## Machine-readable

- `corpus/manifest.json` — per-item provenance, split, domain, action type, structure family, unit/token counts, content hash, and manifest hash.
