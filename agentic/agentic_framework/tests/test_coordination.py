"""
Tests for H16 — Authority-Aware Multi-Agent Coordination.

Required scenarios:
- Capability selection (correct worker selected).
- Authority enforcement (unauthorized delegation rejected).
- Goal ownership (ownership transfers correctly).
- Shared memory (workers observe identical governed state).
- Worker failure (coordinator recovers deterministically).
- Delegation timeout (coordinator handles expiration).
- Budget preservation (all agents consume one shared RunBudget).
- Trace reconstruction (entire coordination history reconstructs).
- Determinism (same mission → identical coordination).

Evidence requirements:
1. Same mission deterministically assigns work to the same qualified agents.
2. Delegation rejected when capability/authority requirements are not met.
3. Goal ownership transfers are explicit and reconstructable.
4. Worker failures do not corrupt shared memory or execution history.
5. All collaborating agents remain bounded by one shared RunBudget.
6. Every coordination decision is reconstructable through the trace.
"""

import pytest

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    RunBudget,
    RunBudgetLimits,
    WorkingMemory,
    # H16
    AgentProfile,
    CapabilityRegistry,
    CoordinationGoal,
    Mission,
    Coordinator,
    AuthorityModel,
    GoalOwnershipLedger,
    ScriptedWorker,
    AgentWorker,
    WorkerResult,
    WorkerUnavailable,
    CoordinationState,
    MissionStatus,
    RejectionReason,
    DelegationContract,
    format_coordination_trace,
)
from agentic.agentic_framework.coordination import COORDINATOR_ID
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _profile(aid, caps, *, perms=frozenset(), trust=0, goals=frozenset()):
    return AgentProfile(
        agent_id=aid, role=aid,
        capabilities=frozenset(caps), permissions=frozenset(perms),
        supported_goals=frozenset(goals), trust_level=trust,
    )


def _ok(outputs):
    return ScriptedWorker(WorkerResult(success=True, outputs=outputs))


def _two_agent_mission():
    reg = CapabilityRegistry()
    reg.register(_profile("research", {"search", "summarize"}, trust=5), _ok({"findings": "F1"}))
    reg.register(_profile("exec", {"invoke"}, trust=1), _ok({"report": "R1"}))
    mission = Mission.of("m1", [
        CoordinationGoal("g1", "research topic", required_capabilities=frozenset({"search"}), expected_outputs=("findings",)),
        CoordinationGoal("g2", "execute", required_capabilities=frozenset({"invoke"}), expected_outputs=("report",)),
    ])
    return reg, mission


# ---------------------------------------------------------------------------
# Agent model
# ---------------------------------------------------------------------------
class TestAgentModel:
    def test_profile_is_immutable(self):
        p = _profile("a", {"x"})
        with pytest.raises(Exception):
            p.agent_id = "b"  # frozen dataclass

    def test_registry_rejects_duplicate(self):
        reg = CapabilityRegistry()
        reg.register(_profile("a", {"x"}), _ok({}))
        with pytest.raises(ValueError):
            reg.register(_profile("a", {"y"}), _ok({}))

    def test_candidates_are_deterministically_ordered(self):
        reg = CapabilityRegistry()
        reg.register(_profile("low", {"search"}, trust=1), _ok({}))
        reg.register(_profile("high", {"search"}, trust=9), _ok({}))
        goal = CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}))
        # Higher trust first.
        assert [p.agent_id for p in reg.candidates_for(goal)] == ["high", "low"]


# ---------------------------------------------------------------------------
# Capability selection & shared memory
# ---------------------------------------------------------------------------
class TestCapabilitySelection:
    def test_correct_worker_selected(self):
        reg, mission = _two_agent_mission()
        mem = WorkingMemory()
        r = Coordinator(reg, mem).run(mission)
        assert r.status == MissionStatus.MISSION_COMPLETED
        assert r.assignment_for("g1").agent_id == "research"
        assert r.assignment_for("g2").agent_id == "exec"

    def test_shared_memory_receives_outputs(self):
        reg, mission = _two_agent_mission()
        mem = WorkingMemory()
        Coordinator(reg, mem).run(mission)
        # Both workers wrote to the SAME store.
        assert mem.peek("findings").value == "F1"
        assert mem.peek("report").value == "R1"
        assert mem.peek("findings").producing_step == "research"


# ---------------------------------------------------------------------------
# Authority enforcement
# ---------------------------------------------------------------------------
class TestAuthorityEnforcement:
    def test_capability_mismatch_rejected(self):
        reg = CapabilityRegistry()
        reg.register(_profile("a", {"summarize"}), _ok({"x": 1}))  # lacks 'search'
        mission = Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), expected_outputs=("x",))])
        r = Coordinator(reg, WorkingMemory()).run(mission)
        assert r.status == MissionStatus.MISSION_FAILED
        assert r.trace.entries[0].reason == RejectionReason.NO_QUALIFIED_AGENT

    def test_authority_denied_rejected(self):
        reg = CapabilityRegistry()
        reg.register(_profile("a", {"search"}, perms=frozenset()), _ok({"x": 1}))
        mission = Mission.of("m", [CoordinationGoal(
            "g", "sensitive", required_capabilities=frozenset({"search"}),
            authority_scope=frozenset({"pii_access"}), expected_outputs=("x",))])
        r = Coordinator(reg, WorkingMemory()).run(mission)
        assert r.status == MissionStatus.MISSION_FAILED
        rej = r.trace.entries[0].rejections[0]
        assert rej["reason"] == RejectionReason.AUTHORITY_DENIED

    def test_authorized_agent_accepted(self):
        reg = CapabilityRegistry()
        reg.register(_profile("a", {"search"}, perms=frozenset({"pii_access"})), _ok({"x": 1}))
        mission = Mission.of("m", [CoordinationGoal(
            "g", "sensitive", required_capabilities=frozenset({"search"}),
            authority_scope=frozenset({"pii_access"}), expected_outputs=("x",))])
        r = Coordinator(reg, WorkingMemory()).run(mission)
        assert r.status == MissionStatus.MISSION_COMPLETED

    def test_authority_check_order_deterministic(self):
        # Capability is checked before authority (fixed order).
        model = AuthorityModel()
        p = _profile("a", set(), perms=frozenset())
        goal = CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), authority_scope=frozenset({"pii"}))
        d = model.authorize(p, goal, None, GoalOwnershipLedger())
        assert d.reason == RejectionReason.CAPABILITY_MISMATCH


# ---------------------------------------------------------------------------
# Goal ownership
# ---------------------------------------------------------------------------
class TestGoalOwnership:
    def test_ownership_transfers_explicitly(self):
        reg, mission = _two_agent_mission()
        r = Coordinator(reg, WorkingMemory()).run(mission)
        g1 = [(t.from_owner, t.to_owner) for t in r.ownership.transfers if t.goal_id == "g1"]
        # Delegated to the worker, then returned to the coordinator.
        assert g1 == [(COORDINATOR_ID, "research"), ("research", COORDINATOR_ID)]

    def test_single_owner_at_a_time(self):
        # During execution the goal is owned by the worker; after, the coordinator.
        reg, mission = _two_agent_mission()
        r = Coordinator(reg, WorkingMemory()).run(mission)
        # Every goal ends owned by the coordinator (released).
        assert r.ownership.owner_of("g1") == COORDINATOR_ID
        assert not r.ownership.is_owned_by_worker("g1")


# ---------------------------------------------------------------------------
# Worker failure recovery
# ---------------------------------------------------------------------------
class TestWorkerFailure:
    def test_recovers_to_next_qualified_agent(self):
        reg = CapabilityRegistry()
        reg.register(_profile("primary", {"search"}, trust=9), ScriptedWorker(WorkerResult(success=False, detail="boom")))
        reg.register(_profile("backup", {"search"}, trust=1), _ok({"y": 2}))
        mem = WorkingMemory()
        mission = Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), expected_outputs=("y",))])
        r = Coordinator(reg, mem).run(mission)
        assert r.status == MissionStatus.MISSION_COMPLETED
        assert r.assignment_for("g").agent_id == "backup"
        assert mem.peek("y").value == 2

    def test_failure_does_not_corrupt_memory(self):
        reg = CapabilityRegistry()
        reg.register(_profile("primary", {"search"}, trust=9), ScriptedWorker(WorkerResult(success=False, outputs={"y": 99})))
        reg.register(_profile("backup", {"search"}, trust=1), _ok({"y": 2}))
        mem = WorkingMemory()
        mission = Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), expected_outputs=("y",))])
        Coordinator(reg, mem).run(mission)
        # The failed worker's output (99) was NEVER committed — only the backup's.
        assert [r.value for r in mem.records("y")] == [2]

    def test_agent_unavailable_recovers(self):
        def raiser(contract, memory):
            raise WorkerUnavailable("down")
        reg = CapabilityRegistry()
        reg.register(_profile("primary", {"search"}, trust=9), ScriptedWorker(raiser))
        reg.register(_profile("backup", {"search"}, trust=1), _ok({"y": 5}))
        r = Coordinator(reg, WorkingMemory()).run(
            Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), expected_outputs=("y",))]))
        assert r.status == MissionStatus.MISSION_COMPLETED
        assert r.assignment_for("g").agent_id == "backup"

    def test_all_fail_mission_fails(self):
        reg = CapabilityRegistry()
        reg.register(_profile("a", {"search"}, trust=2), ScriptedWorker(WorkerResult(success=False)))
        reg.register(_profile("b", {"search"}, trust=1), ScriptedWorker(WorkerResult(success=False)))
        r = Coordinator(reg, WorkingMemory()).run(
            Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), expected_outputs=("y",))]))
        assert r.status == MissionStatus.MISSION_FAILED


# ---------------------------------------------------------------------------
# Delegation timeout
# ---------------------------------------------------------------------------
class TestDelegationTimeout:
    def test_timeout_flag_recovers(self):
        reg = CapabilityRegistry()
        reg.register(_profile("slow", {"search"}, trust=9), ScriptedWorker(WorkerResult(success=True, timed_out=True)))
        reg.register(_profile("fast", {"search"}, trust=1), _ok({"z": 3}))
        mem = WorkingMemory()
        r = Coordinator(reg, mem).run(
            Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), timeout=1.0, expected_outputs=("z",))]))
        assert r.status == MissionStatus.MISSION_COMPLETED
        assert mem.peek("z").value == 3

    def test_duration_over_timeout_recovers(self):
        reg = CapabilityRegistry()
        reg.register(_profile("slow", {"search"}, trust=9), ScriptedWorker(WorkerResult(success=True, outputs={"z": 1}, duration=5.0)))
        reg.register(_profile("fast", {"search"}, trust=1), _ok({"z": 3}))
        r = Coordinator(reg, WorkingMemory()).run(
            Mission.of("m", [CoordinationGoal("g", "d", required_capabilities=frozenset({"search"}), timeout=2.0, expected_outputs=("z",))]))
        assert r.assignment_for("g").agent_id == "fast"


# ---------------------------------------------------------------------------
# Budget preservation
# ---------------------------------------------------------------------------
class TestBudgetPreservation:
    def test_all_agents_share_one_budget(self):
        reg, mission = _two_agent_mission()
        budget = RunBudget(RunBudgetLimits())
        Coordinator(reg, WorkingMemory(), run_budget=budget).run(mission)
        # One delegation (handoff) per goal, all on the same budget.
        assert budget.usage.handoffs == 2

    def test_agent_workers_consume_shared_budget(self):
        def agent():
            a = build_agent(adapter=MockLLMAdapter(default_response="done"),
                            use_llm_for_decomposition=False, max_revisions=0)
            a.safety_gate = SafetyGate(SafetyContractEvaluator(0.0, 0.0, 1.0, 0.0))
            return a
        reg = CapabilityRegistry()
        reg.register(_profile("w1", {"search"}, trust=2), AgentWorker(agent()))
        reg.register(_profile("w2", {"invoke"}, trust=1), AgentWorker(agent()))
        mission = Mission.of("m", [
            CoordinationGoal("g1", "do a", required_capabilities=frozenset({"search"}), expected_outputs=("a",)),
            CoordinationGoal("g2", "do b", required_capabilities=frozenset({"invoke"}), expected_outputs=("b",)),
        ])
        budget = RunBudget(RunBudgetLimits())
        mem = WorkingMemory()
        r = Coordinator(reg, mem, run_budget=budget).run(mission)
        assert r.status == MissionStatus.MISSION_COMPLETED
        # Both worker agents' model calls landed on the ONE shared budget.
        assert budget.usage.model_calls == 2
        assert budget.usage.handoffs == 2

    def test_budget_exhaustion_stops_coordination(self):
        reg = CapabilityRegistry()
        for i in range(6):
            reg.register(_profile(f"a{i}", {"search"}, trust=i), _ok({f"k{i}": i}))
        goals = [CoordinationGoal(f"g{i}", "d", goal_type=f"t{i}", required_capabilities=frozenset({"search"}),
                                  expected_outputs=(f"k{i}",)) for i in range(6)]
        # Give each agent a distinct goal type so each goal maps to one agent.
        reg2 = CapabilityRegistry()
        for i in range(6):
            reg2.register(_profile(f"a{i}", {"search"}, trust=1, goals={f"t{i}"}), _ok({f"k{i}": i}))
        budget = RunBudget(RunBudgetLimits(max_handoffs=2))
        r = Coordinator(reg2, WorkingMemory(), run_budget=budget).run(Mission.of("m", goals))
        assert r.status == MissionStatus.BUDGET_EXHAUSTED
        assert budget.usage.handoffs == 2


# ---------------------------------------------------------------------------
# Determinism & trace reconstruction
# ---------------------------------------------------------------------------
class TestDeterminismAndTrace:
    def test_same_mission_identical_coordination(self):
        def build():
            reg = CapabilityRegistry()
            reg.register(_profile("research", {"search", "summarize"}, trust=5), _ok({"findings": "F"}))
            reg.register(_profile("exec", {"invoke"}, trust=1), _ok({"report": "R"}))
            return reg
        mission = Mission.of("m", [
            CoordinationGoal("g1", "r", required_capabilities=frozenset({"search"}), expected_outputs=("findings",)),
            CoordinationGoal("g2", "e", required_capabilities=frozenset({"invoke"}), expected_outputs=("report",)),
        ])
        t1 = Coordinator(build(), WorkingMemory()).run(mission).to_dict()["trace"]
        t2 = Coordinator(build(), WorkingMemory()).run(mission).to_dict()["trace"]
        assert t1 == t2

    def test_trace_reconstructs_full_history(self):
        reg, mission = _two_agent_mission()
        r = Coordinator(reg, WorkingMemory()).run(mission)
        entries = r.trace.entries
        assert [e.decision for e in entries] == ["COMPLETED", "COMPLETED"]
        # Each entry reconstructs contract, worker result, memory writes, ownership.
        e0 = entries[0]
        assert e0.agent_id == "research"
        assert e0.contract["assigned_agent"] == "research"
        assert e0.memory_writes == ["findings"]
        assert e0.ownership_from == "research" and e0.ownership_to == COORDINATOR_ID
        assert "Coordination" in format_coordination_trace(r)

    def test_assignment_lifecycle_is_append_only(self):
        reg, mission = _two_agent_mission()
        r = Coordinator(reg, WorkingMemory()).run(mission)
        a = r.assignment_for("g1")
        states = [t.to_state for t in a.history]
        assert states == [
            CoordinationState.ASSIGNED,
            CoordinationState.ACCEPTED,
            CoordinationState.EXECUTING,
            CoordinationState.COMPLETED,
        ]


# ---------------------------------------------------------------------------
# Evidence 1 (headline)
# ---------------------------------------------------------------------------
class TestEvidence:
    def test_evidence1_same_mission_same_qualified_agents(self):
        # Two qualified researchers; the higher-trust one is always chosen.
        def build():
            reg = CapabilityRegistry()
            reg.register(_profile("senior", {"search"}, trust=9), _ok({"findings": "F"}))
            reg.register(_profile("junior", {"search"}, trust=1), _ok({"findings": "F"}))
            return reg
        mission = Mission.of("m", [CoordinationGoal("g", "research", required_capabilities=frozenset({"search"}), expected_outputs=("findings",))])
        a = Coordinator(build(), WorkingMemory()).run(mission).assignment_for("g").agent_id
        b = Coordinator(build(), WorkingMemory()).run(mission).assignment_for("g").agent_id
        assert a == b == "senior"
