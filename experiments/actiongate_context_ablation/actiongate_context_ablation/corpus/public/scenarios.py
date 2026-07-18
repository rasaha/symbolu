"""PUBLIC_NATURALISTIC_CORPUS — repository-derived contexts.

Every item is adapted from real material that already exists in the rasaha/symbolu
repository (manifests, CI workflows, the frozen policy ruleset, gateway/k8s/MCP
demo scenarios). None was authored for this experiment. Provenance records the
exact repo path, license (repo-internal / vendored), and the adaptation applied
(transforming a manifest / policy rule / scenario into an ActionGate request
context; only field names and short structural excerpts are used).

PROVENANCE NOTE: repository-derived material is NOT confidential customer
operational data. It cannot emit REAL_CUSTOMER_VALIDATED.
"""

from __future__ import annotations

from ..builders import prov
from ..schema import (
    DEV, HELDOUT, PROSE, PROSE_TABLES, PUBLIC, STRUCTURED, VALIDATION,
)

# (action_type, domain, [(split, service, structure), ...], repo_source, title, adaptation)
# Each action type carries DEV / VALIDATION / HELDOUT variants with distinct
# targets so no template_family leaks across splits.
_PLAN = [
    ("kubernetes_deploy", "kubernetes",
     [(DEV, "svc://checkout", PROSE), (VALIDATION, "svc://catalog", PROSE_TABLES),
      (HELDOUT, "svc://search", PROSE)],
     "deploy/gke/deployment.yaml", "GKE demo Deployment manifest",
     "Transformed the Deployment/rollout manifest into a kubernetes apply request context."),
    ("kubernetes_delete", "kubernetes",
     [(DEV, "db://replica/3", PROSE), (VALIDATION, "db://replica/6", PROSE),
      (HELDOUT, "db://replica/9", PROSE)],
     "cyber_security/action_gateway_k8s/demos/scenarios.py",
     "k8s gateway delete enforcement scenario",
     "Adapted a k8s delete enforcement demo into a naturalistic delete ticket context."),
    ("terraform_apply", "terraform",
     [(DEV, "svc://billing", PROSE), (VALIDATION, "svc://payments-tf", PROSE_TABLES),
      (HELDOUT, "svc://ledger-tf", PROSE)],
     "cyber_security/action_gateway/demos/scenarios.py",
     "gateway terraform apply scenario",
     "Adapted the terraform apply enforcement scenario into a change ticket context."),
    ("release_promotion", "cicd",
     [(DEV, "svc://api-gw", PROSE), (VALIDATION, "svc://web-fe", PROSE),
      (HELDOUT, "svc://mobile-bff", PROSE)],
     ".github/workflows/pipeline-ci.yml", "pipeline CI workflow",
     "Transformed a CI promotion workflow into a release-promotion deploy context."),
    ("service_rollback", "cicd",
     [(DEV, "svc://orders", PROSE), (VALIDATION, "svc://shipping", PROSE),
      (HELDOUT, "svc://inventory", PROSE)],
     "deploy/gke/deployment.yaml", "GKE Deployment manifest (rollback path)",
     "Used the Deployment manifest revision fields to frame a rollback deploy context."),
    ("iam_grant", "iam",
     [(DEV, "iam://role/admin-a", PROSE), (VALIDATION, "iam://role/admin-b", PROSE),
      (HELDOUT, "iam://role/admin-c", PROSE)],
     "cyber_security/action_gate_reference/action_gate_ref/policy.py",
     "policy R1 IAM_GRANT_ADMIN ruleset",
     "Instantiated the R1 IAM_GRANT_ADMIN rule into a grant request with approval + attestation spans."),
    ("credential_scope_change", "iam",
     [(DEV, "file://secrets/svc-a", STRUCTURED), (VALIDATION, "file://secrets/svc-b", STRUCTURED),
      (HELDOUT, "file://secrets/svc-c", STRUCTURED)],
     "cyber_security/action_gateway_mcp/action_gateway_mcp/registry.py",
     "MCP tool registry credential scope",
     "Adapted the MCP credential-scope registry into a scope-change request context."),
    ("secret_export", "secrets",
     [(DEV, "file://secrets/db", PROSE), (VALIDATION, "file://secrets/kv", PROSE_TABLES),
      (HELDOUT, "file://secrets/api", PROSE)],
     "cyber_security/action_gate_reference/action_gate_ref/policy.py",
     "policy R5 SECRET_READ ruleset",
     "Instantiated the R5 SECRET_READ export rule into a secret-export ticket context."),
    ("customer_data_export", "secrets",
     [(DEV, "file://secrets/crm", PROSE), (VALIDATION, "file://secrets/pii", PROSE),
      (HELDOUT, "file://secrets/audit", PROSE)],
     "cyber_security/action_gate_reference/action_gate_ref/policy.py",
     "policy R5 SECRET_READ (export)",
     "Adapted R5 into a customer-data export request with an approved-sink span."),
    ("network_policy", "network",
     [(DEV, "net://svc/edge", PROSE), (VALIDATION, "net://svc/admin", PROSE),
      (HELDOUT, "net://svc/gw", PROSE)],
     "deploy/gke/rbac.yaml", "GKE RBAC / network exposure manifest",
     "Transformed an RBAC/exposure manifest into a network-policy widening context."),
    ("database_migration", "database",
     [(DEV, "db://orders", PROSE_TABLES), (VALIDATION, "db://accounts", STRUCTURED),
      (HELDOUT, "db://ledger", PROSE_TABLES)],
     "cyber_security/action_gateway/demos/scenarios.py",
     "gateway DB mutation scenario",
     "Adapted the DB mutation enforcement scenario into a migration ticket with a row-count table."),
    ("monitoring_disable", "monitoring",
     [(DEV, "mon://alerts/prod", PROSE), (VALIDATION, "mon://alerts/pager", PROSE),
      (HELDOUT, "mon://alerts/edge", PROSE)],
     "cyber_security/action_gate_reference/action_gate_ref/policy.py",
     "policy R6 MONITORING_DISABLE ruleset",
     "Instantiated R6 into a maintenance-window monitoring-disable context."),
    ("cloud_storage_delete", "storage",
     [(DEV, "file://bucket/logs-a", PROSE), (VALIDATION, "file://bucket/logs-b", PROSE),
      (HELDOUT, "file://bucket/logs-c", PROSE)],
     "cyber_security/action_gate_reference/action_gate_ref/policy.py",
     "policy R3 DB_DELETE ruleset",
     "Instantiated R3 into a cloud-storage bucket deletion context."),
    ("branch_protection", "repo",
     [(DEV, "repo://main/protect-a", STRUCTURED), (VALIDATION, "repo://main/protect-b", STRUCTURED),
      (HELDOUT, "repo://main/protect-c", STRUCTURED)],
     ".github/workflows/backbone-ci.yml", "backbone CI workflow",
     "Adapted a CI/branch policy workflow into a branch-protection change context."),
]


def _redundant_for(action_type, split):
    # sprinkle redundancy on a subset (deterministic) to exercise redundancy-set ablation
    return action_type in ("secret_export", "database_migration") and split != HELDOUT


def _build_specs():
    specs = []
    for action_type, domain, variants, source, title, adaptation in _PLAN:
        for split, service, structure in variants:
            sid = f"pub_{action_type}_{split.lower()}_{service.split('/')[-1]}".replace(":", "")
            expected_env = f"{action_type} -> {domain} operation envelope"
            fillers = ("justify", "history", "logs") if structure != STRUCTURED \
                else ("justify", "logs", "stale")
            specs.append({
                "item_id": sid, "partition": PUBLIC, "split": split, "domain": domain,
                "action_type": action_type, "structure_family": structure,
                "target": (service,), "fillers": fillers,
                "template_family": f"pub:{action_type}:{service}",
                "redundant": _redundant_for(action_type, split),
                "provenance": prov(
                    source=source, title=title, license="repo-internal (rasaha/symbolu)",
                    adaptations=adaptation, action_type=action_type, tool_domain=domain,
                    expected_envelope=expected_env, adapted=True,
                    retrieved="2026-07-13 (repo checkout)"),
            })
    return specs


SPECS = _build_specs()
