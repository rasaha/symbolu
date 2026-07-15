"""Legacy-vs-new parity corpus (16 scenarios, labeled).

Each scenario carries a shared model plan (used to drive BOTH the legacy
``decompose_goal`` and the new ``ModelPlanner`` deterministically) and a label:

    PARITY                 - decomposition + execution expected to agree
    INTENTIONAL_DIFFERENCE - decomposition may agree, but execution/governance differs
                             by design (legacy governs in-runtime; new delegates to the
                             AI Control Plane)
    UNSUPPORTED_LEGACY     - behavior the legacy runtime cannot express
    UNSUPPORTED_MIGRATION  - behavior the new runtime does not support this phase

The shared model plan sets BOTH legacy field names (``type``/``parameters``) and new
field names (``tool``/``arguments``) to identical values so the decomposition is
directly comparable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..contracts.action import RiskClass

PARITY = "PARITY"
INTENTIONAL_DIFFERENCE = "INTENTIONAL_DIFFERENCE"
UNSUPPORTED_LEGACY = "UNSUPPORTED_LEGACY"
UNSUPPORTED_MIGRATION = "UNSUPPORTED_MIGRATION"


def _step(tool: str, args: Dict[str, Any] | None = None, desc: str = ""):
    args = args or {}
    return {"type": tool, "tool": tool, "description": desc, "parameters": args, "arguments": args}


def _db_args(**over):
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    op.update(over.pop("op", {}))
    scope = over.pop("affected_scope", {"estimated_rows": "42", "unbounded": False})
    return {"actuation": {"operation": "DB_MUTATION",
                          "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
                          "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
                          "affected_scope": scope,
                          "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
                          "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
                          "reversibility": "REVERSIBLE_WITH_COST"},
            "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                              "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def _k8s_scale_args():
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10, "available_replicas": 10,
          "readiness_plasticity": 0.95, "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    return {"actuation": {"operation": "DEPLOY",
                          "target": {"cluster": "fixture", "namespace": "protected", "deployment": "web"},
                          "arguments": {"replicas": "12"},
                          "requested_state_transition": {"replicas": {"from": "10", "to": "12"}},
                          "reversibility": "REVERSIBLE"},
            "authority": {"principal": "agent:web-ops", "permissions": ["deploy"],
                          "delegator": {"id": "sre", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "1001", "state_hash": "sha-256:" + "ab" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "kubernetes",
                              "correlation_id": "protected/web", "sequence_id": "1", "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def _k8s_rollout_args():
    a = _k8s_scale_args()
    a["actuation"] = {"operation": "DEPLOY",
                      "target": {"cluster": "fixture", "namespace": "protected", "deployment": "web"},
                      "image_digest": "sha256:" + "cd" * 32,
                      "current_manifest_digest": "sha256:" + "ef" * 32,
                      "rollout_strategy": "RollingUpdate", "max_surge": "1", "max_unavailable": "0",
                      "timeout_s": "600", "rollback_ref": "web-rev-41", "reversibility": "REVERSIBLE_WITH_COST"}
    return a


# tool -> (risk_class, profile, fast_path)
READ = (RiskClass.LOCAL_READ_ONLY, None, True)
GOV_DB = (RiskClass.GOVERNED_CONSEQUENTIAL, "database.mutation.v1", False)
GOV_SCALE = (RiskClass.GOVERNED_CONSEQUENTIAL, "kubernetes.scale.v1", False)
GOV_ROLL = (RiskClass.GOVERNED_CONSEQUENTIAL, "kubernetes.rollout.v1", False)


@dataclass
class ParityScenario:
    name: str
    task: str
    plan: List[Dict[str, Any]]
    tools: Dict[str, tuple]                 # tool_name -> (risk_class, profile, fast_path)
    label: str
    governed: bool = False
    expect_new_outcome: str = ""            # composed outcome for governed scenarios
    fail_local_tool: bool = False
    auto_evidence: bool = True


def build_corpus() -> List[ParityScenario]:
    return [
        ParityScenario("read_only_research", "research the retry policy",
                       [_step("search", {"q": "retry"})], {"search": READ}, PARITY),
        ParityScenario("multi_step_info_gathering", "gather and summarize",
                       [_step("search", {"q": "a"}), _step("search", {"q": "b"}), _step("generate")],
                       {"search": READ, "generate": READ}, PARITY),
        ParityScenario("structured_extraction", "extract fields",
                       [_step("validate", {"schema": "x"})], {"validate": READ}, PARITY),
        ParityScenario("file_analysis", "analyze the file",
                       [_step("compute", {"path": "f"})], {"compute": READ}, PARITY),
        ParityScenario("local_deterministic_transformation", "transform locally",
                       [_step("compute", {"op": "upper"})], {"compute": READ}, PARITY),
        ParityScenario("kubernetes_scale_proposal", "scale web to 12",
                       [_step("kubernetes.scale", _k8s_scale_args())], {"kubernetes.scale": GOV_SCALE},
                       INTENTIONAL_DIFFERENCE, governed=True, expect_new_outcome="PROCEED"),
        ParityScenario("kubernetes_rollout_proposal", "roll out new image",
                       [_step("kubernetes.rollout", _k8s_rollout_args())], {"kubernetes.rollout": GOV_ROLL},
                       INTENTIONAL_DIFFERENCE, governed=True, expect_new_outcome="PROCEED"),
        ParityScenario("database_mutation_proposal", "update orders",
                       [_step("database.mutation", _db_args())], {"database.mutation": GOV_DB},
                       INTENTIONAL_DIFFERENCE, governed=True, expect_new_outcome="PROCEED"),
        ParityScenario("authorization_denial", "unbounded update",
                       [_step("database.mutation", _db_args(affected_scope={"estimated_rows": "1", "unbounded": True}))],
                       {"database.mutation": GOV_DB}, INTENTIONAL_DIFFERENCE, governed=True,
                       expect_new_outcome="BLOCKED_BY_AUTHORIZATION"),
        ParityScenario("acp_operational_hold", "update during freeze",
                       [_step("database.mutation", _db_args(op={"freeze_active": True}))],
                       {"database.mutation": GOV_DB}, INTENTIONAL_DIFFERENCE, governed=True,
                       expect_new_outcome="HELD_BY_ACP"),
        ParityScenario("more_evidence_request", "update without evidence",
                       [_step("database.mutation", _db_args())], {"database.mutation": GOV_DB},
                       INTENTIONAL_DIFFERENCE, governed=True, expect_new_outcome="PENDING_AUTHORIZATION",
                       auto_evidence=False),
        ParityScenario("human_escalation", "held requires human",
                       [_step("database.mutation", _db_args(op={"freeze_active": True}))],
                       {"database.mutation": GOV_DB}, INTENTIONAL_DIFFERENCE, governed=True,
                       expect_new_outcome="HELD_BY_ACP"),
        ParityScenario("execution_failure", "local tool fails",
                       [_step("compute", {"op": "x"})], {"compute": READ}, INTENTIONAL_DIFFERENCE,
                       fail_local_tool=True),
        ParityScenario("retry", "flaky then ok",
                       [_step("compute", {"op": "x"})], {"compute": READ}, INTENTIONAL_DIFFERENCE),
        ParityScenario("cancellation", "cancel run",
                       [_step("search", {"q": "x"})], {"search": READ}, PARITY),
        ParityScenario("observation_reflection_replan", "denied then replan",
                       [_step("database.mutation", _db_args(affected_scope={"estimated_rows": "1", "unbounded": True}))],
                       {"database.mutation": GOV_DB}, INTENTIONAL_DIFFERENCE, governed=True,
                       expect_new_outcome="BLOCKED_BY_AUTHORIZATION"),
    ]
