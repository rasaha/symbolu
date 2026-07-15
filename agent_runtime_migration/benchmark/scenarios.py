"""Deterministic migration scenario suite.

Each scenario builds a Goal + a trusted tool registry + a governed executor and
declares its expected outcome. Scenarios cover: read-only, multi-step, a governed
Kubernetes action, a governed database mutation, a denied action, an ACP operational
hold, an execution failure, cancellation, human intervention, and
observation->reflection->replan. Deterministic (fixed ``now``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..contracts.action import Action, RiskClass
from ..contracts.goal import Goal
from ..control_plane import ControlPlaneClient, GovernedExecutor
from ..runtime import CancellationToken
from ..tools import ToolRegistry

NOW = "2026-01-01T00:10:00.000Z"


class Spy:
    def __init__(self, ret="OK"):
        self.calls = 0
        self._ret = ret

    def __call__(self, args):
        self.calls += 1
        return self._ret


def _fail(args):
    raise RuntimeError("tool failure")


# ---- envelope fixtures ----
def _db_env(**op_over):
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    op.update(op_over)
    return {"authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                              "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def _db_action(action_id="m", **act_over):
    actuation = {"operation": "DB_MUTATION",
                 "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
                 "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
                 "affected_scope": {"estimated_rows": "42", "unbounded": False},
                 "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
                 "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
                 "reversibility": "REVERSIBLE_WITH_COST"}
    env_over = act_over.pop("env", {})
    actuation.update(act_over)
    args = {"actuation": actuation}
    args.update(_db_env(**env_over))
    return Action(action_id=action_id, kind="database.mutation", tool_name="db.mutation",
                  risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1", arguments=args)


def _k8s_env():
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10, "available_replicas": 10,
          "readiness_plasticity": 0.95, "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
          "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    return {"authority": {"principal": "agent:web-ops", "permissions": ["deploy"],
                          "delegator": {"id": "sre", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "1001", "state_hash": "sha-256:" + "ab" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "kubernetes",
                              "correlation_id": "protected/web", "sequence_id": "1", "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def _k8s_scale_action(action_id="k"):
    actuation = {"operation": "DEPLOY",
                 "target": {"cluster": "fixture", "namespace": "protected", "deployment": "web"},
                 "arguments": {"replicas": "12"},
                 "requested_state_transition": {"replicas": {"from": "10", "to": "12"}},
                 "reversibility": "REVERSIBLE"}
    args = {"actuation": actuation}
    args.update(_k8s_env())
    return Action(action_id=action_id, kind="kubernetes.scale", tool_name="k8s.scale",
                  risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="kubernetes.scale.v1", arguments=args)


def _local(action_id, tool="read.doc"):
    return Action(action_id=action_id, kind="read", tool_name=tool,
                  risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})


@dataclass
class Scenario:
    name: str
    goal: Goal
    registry: ToolRegistry
    spy: Spy
    expect_status: str
    expect_executed: int          # number of governed tool executions expected
    expect_governed: bool
    cancellation: Optional[CancellationToken] = None
    max_replans: int = 2

    def executor(self) -> GovernedExecutor:
        return GovernedExecutor(registry=self.registry, client=ControlPlaneClient(auto_evidence=self._auto),
                                now_provider=lambda: NOW)
    _auto: bool = True


def _reg(spy, *, governed_tool=None, profile=None, local_tools=("read.doc",)):
    r = ToolRegistry()
    for t in local_tools:
        r.register(t, spy, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    if governed_tool:
        r.register(governed_tool, spy, RiskClass.GOVERNED_CONSEQUENTIAL, profile=profile)
    return r


def build_scenarios() -> List[Scenario]:
    S: List[Scenario] = []

    # 1. read-only research
    sp = Spy("DOC"); S.append(Scenario(
        "read_only_research", Goal(goal_id="s1", objective="research",
        metadata={"plan": [_local("a")]}), _reg(sp), sp, "completed", 1, False))

    # 2. multi-step local workflow
    sp = Spy("DOC"); S.append(Scenario(
        "multi_step_workflow", Goal(goal_id="s2", objective="multi",
        metadata={"plan": [_local("a"), _local("b"), _local("c")]}), _reg(sp), sp, "completed", 3, False))

    # 3. governed Kubernetes scale (proceed)
    sp = Spy(); S.append(Scenario(
        "kubernetes_scale_proceed", Goal(goal_id="s3", objective="scale",
        metadata={"plan": [_k8s_scale_action("k")]}),
        _reg(sp, governed_tool="k8s.scale", profile="kubernetes.scale.v1"), sp, "completed", 1, True))

    # 4. governed database mutation (proceed)
    sp = Spy(); S.append(Scenario(
        "database_mutation_proceed", Goal(goal_id="s4", objective="db",
        metadata={"plan": [_db_action("m")]}),
        _reg(sp, governed_tool="db.mutation", profile="database.mutation.v1"), sp, "completed", 1, True))

    # 5. denied action (unbounded -> BLOCKED)
    sp = Spy(); S.append(Scenario(
        "denied_action", Goal(goal_id="s5", objective="denied",
        metadata={"plan": [_db_action("m", affected_scope={"estimated_rows": "1", "unbounded": True})]}),
        _reg(sp, governed_tool="db.mutation", profile="database.mutation.v1"), sp,
        "stopped", 0, True, max_replans=0))

    # 6. ACP operational hold (freeze)
    sp = Spy(); S.append(Scenario(
        "acp_operational_hold", Goal(goal_id="s6", objective="held",
        metadata={"plan": [_db_action("m", env={"freeze_active": True})]}),
        _reg(sp, governed_tool="db.mutation", profile="database.mutation.v1"), sp,
        "awaiting_human", 0, True))

    # 7. execution failure (local tool raises)
    sp = Spy(); reg = ToolRegistry(); reg.register("boom", _fail, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    S.append(Scenario("execution_failure", Goal(goal_id="s7", objective="fail",
        metadata={"plan": [_local("a", "boom")]}), reg, sp, "stopped", 0, False))

    # 8. cancellation
    sp = Spy("DOC"); tok = CancellationToken(); tok.cancel()
    S.append(Scenario("cancellation", Goal(goal_id="s8", objective="cancel",
        metadata={"plan": [_local("a")]}), _reg(sp), sp, "cancelled", 0, False, cancellation=tok))

    # 9. human intervention (pending, no evidence)
    sp = Spy(); sc = Scenario("human_intervention", Goal(goal_id="s9", objective="pending",
        metadata={"plan": [_db_action("m")]}),
        _reg(sp, governed_tool="db.mutation", profile="database.mutation.v1"), sp,
        "awaiting_human", 0, True)
    sc._auto = False  # force PENDING_AUTHORIZATION
    S.append(sc)

    # 10. observation -> reflection -> replan (denied, allow one replan -> completes)
    sp = Spy(); S.append(Scenario(
        "observe_reflect_replan", Goal(goal_id="s10", objective="replan",
        metadata={"plan": [_db_action("m", affected_scope={"estimated_rows": "1", "unbounded": True})]}),
        _reg(sp, governed_tool="db.mutation", profile="database.mutation.v1"), sp,
        "completed", 0, True, max_replans=1))

    return S
