"""AUTHORED_REALISTIC_CORPUS — independently authored enterprise scenarios.

These were written to resemble real enterprise change contexts (request +
justification + state + approval + policy excerpt + rollback + simulation + logs +
irrelevant history + duplicated/stale facts), NOT to force any verdict. They are
authored, not harvested — clearly labelled, and NOT confidential customer data.
They cannot emit REAL_CUSTOMER_VALIDATED.

Distinct target names from the public partition prevent template-family leakage.
"""

from __future__ import annotations

from ..builders import prov
from ..schema import (
    AUTHORED, DEV, HELDOUT, PROSE, PROSE_TABLES, STRUCTURED, VALIDATION,
)

# (action_type, domain, [(split, service, structure, fillers), ...])
_PLAN = [
    ("kubernetes_deploy", "kubernetes",
     [(DEV, "svc://profile", PROSE, ("justify", "history", "logs")),
      (VALIDATION, "svc://notify", PROSE_TABLES, ("justify", "logs", "stale")),
      (HELDOUT, "svc://feed", PROSE, ("justify", "history"))]),
    ("kubernetes_delete", "kubernetes",
     [(DEV, "db://shard/2", PROSE, ("justify", "history", "logs")),
      (HELDOUT, "db://shard/8", PROSE, ("history", "stale"))]),
    ("terraform_apply", "terraform",
     [(DEV, "svc://gateway-tf", PROSE, ("justify", "logs")),
      (VALIDATION, "svc://cache-tf", PROSE_TABLES, ("justify", "history", "logs", "stale")),
      (HELDOUT, "svc://queue-tf", PROSE, ("history",))]),
    ("release_promotion", "cicd",
     [(DEV, "svc://auth-svc", PROSE, ("justify", "logs")),
      (HELDOUT, "svc://billing-fe", PROSE, ("justify", "history"))]),
    ("service_rollback", "cicd",
     [(DEV, "svc://payments-core", PROSE, ("justify", "history", "logs")),
      (VALIDATION, "svc://fulfillment", PROSE, ("history", "stale"))]),
    ("iam_grant", "iam",
     [(DEV, "iam://role/deploy-a", PROSE, ("justify", "history")),
      (VALIDATION, "iam://role/deploy-b", PROSE, ("justify", "logs", "stale")),
      (HELDOUT, "iam://role/deploy-c", PROSE, ("history",))]),
    ("credential_scope_change", "iam",
     [(DEV, "file://secrets/app-a", STRUCTURED, ("justify", "logs")),
      (HELDOUT, "file://secrets/app-c", STRUCTURED, ("stale",))]),
    ("secret_export", "secrets",
     [(DEV, "file://secrets/warehouse", PROSE, ("justify", "history", "logs")),
      (VALIDATION, "file://secrets/analytics", PROSE_TABLES, ("justify", "stale")),
      (HELDOUT, "file://secrets/exportsvc", PROSE, ("history",))]),
    ("network_policy", "network",
     [(DEV, "net://svc/ingress-a", PROSE, ("justify", "logs")),
      (VALIDATION, "net://svc/ingress-b", PROSE, ("justify", "history", "stale")),
      (HELDOUT, "net://svc/ingress-c", PROSE, ("history",))]),
    ("database_migration", "database",
     [(DEV, "db://users", PROSE_TABLES, ("justify", "history", "logs")),
      (VALIDATION, "db://sessions", STRUCTURED, ("logs", "stale")),
      (HELDOUT, "db://events", PROSE_TABLES, ("history",))]),
    ("monitoring_disable", "monitoring",
     [(DEV, "mon://alerts/db", PROSE, ("justify", "logs")),
      (HELDOUT, "mon://alerts/net", PROSE, ("stale",))]),
    ("payment_refund", "payments",
     [(DEV, "db://payments/refunds-a", STRUCTURED, ("justify", "logs")),
      (VALIDATION, "db://payments/refunds-b", STRUCTURED, ("justify", "history", "stale")),
      (HELDOUT, "db://payments/refunds-c", STRUCTURED, ("history",))]),
    ("cloud_storage_delete", "storage",
     [(DEV, "file://bucket/backups-a", PROSE, ("justify", "history", "logs")),
      (HELDOUT, "file://bucket/backups-c", PROSE, ("stale",))]),
    ("incident_mitigation", "monitoring",
     [(DEV, "mon://alerts/latency", PROSE, ("justify", "logs")),
      (VALIDATION, "mon://alerts/errors", PROSE, ("history", "stale"))]),
]


def _redundant_for(action_type, split):
    return action_type in ("iam_grant", "secret_export", "kubernetes_delete") and split == DEV


def _build_specs():
    specs = []
    for action_type, domain, variants in _PLAN:
        for split, service, structure, fillers in variants:
            sid = f"auth_{action_type}_{split.lower()}_{service.split('/')[-1]}".replace(":", "")
            specs.append({
                "item_id": sid, "partition": AUTHORED, "split": split, "domain": domain,
                "action_type": action_type, "structure_family": structure,
                "target": (service,), "fillers": fillers,
                "template_family": f"auth:{action_type}:{service}",
                "redundant": _redundant_for(action_type, split),
                "provenance": prov(
                    source="authored_realistic", title=f"authored {action_type} scenario",
                    license="original-authored", adapted=False,
                    adaptations="none (independently authored realistic scenario)",
                    action_type=action_type, tool_domain=domain,
                    expected_envelope=f"{action_type} -> {domain} operation envelope"),
            })
    return specs


SPECS = _build_specs()
