"""
Tests for multi-agent orchestration & handoff.

Covers:
- Registry registration / lookup / roster.
- KeywordRouter deterministic handoff (agent A -> agent B).
- Each agent runs its own governed pipeline (tool execution preserved).
- LLMRouter supervisor routing.
- max_handoffs is a hard, terminal bound.
- Completion markers stop the run.
"""

import json

import pytest

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    SequentialMockAdapter,
    ToolSpec,
    ToolRiskLevel,
    AgentRegistry,
    KeywordRouter,
    LLMRouter,
    MultiAgentOrchestrator,
    RouteDecision,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _open_gate():
    """A gate whose evaluator always returns eligible (governance still runs)."""
    return SafetyGate(
        SafetyContractEvaluator(
            consistency_threshold=0.0,
            alignment_threshold=0.0,
            reversal_risk_threshold=1.0,
            stability_threshold=0.0,
        )
    )

SEARCH_DECOMP = json.dumps(
    {
        "purpose": "research",
        "purpose_type": "task",
        "reasoning_strategy": "search",
        "agency_level": "FULL",
        "actions": [
            {"description": "look it up", "type": "search", "parameters": {"query": "x"}}
        ],
    }
)


def _agent(default_response, responses=None, tools=None):
    a = build_agent(
        adapter=MockLLMAdapter(responses=responses or {}, default_response=default_response),
        tools=tools or {},
    )
    a.safety_gate = _open_gate()
    return a


def _team():
    researcher = _agent(
        "Facts collected. Please write and draft the final summary.",
        responses={"extract structured goal information": SEARCH_DECOMP},
        tools={
            "search": ToolSpec(
                handler=lambda p: {"facts": ["solar", "wind"]},
                description="search",
                risk_level=ToolRiskLevel.READ_ONLY,
            )
        },
    )
    writer = _agent("Renewable energy summary: solar and wind lead. [final]")
    reg = AgentRegistry()
    reg.register("researcher", researcher, "Finds facts with a search tool")
    reg.register("writer", writer, "Writes prose summaries")
    return reg


class TestRegistry:
    def test_register_and_lookup(self):
        reg = _team()
        assert reg.has("researcher") and reg.has("writer")
        assert set(reg.names()) == {"researcher", "writer"}
        assert "researcher" in reg.roster()
        assert len(reg) == 2

    def test_duplicate_registration_rejected(self):
        reg = _team()
        with pytest.raises(ValueError):
            reg.register("writer", _agent("x"), "dup")

    def test_unknown_agent_raises(self):
        reg = _team()
        with pytest.raises(KeyError):
            reg.get("nobody")


class TestKeywordHandoff:
    def test_researcher_hands_off_to_writer(self):
        reg = _team()
        router = KeywordRouter(
            routes={
                "researcher": ["research", "find", "facts about"],
                "writer": ["write", "draft", "summary"],
            },
            default="researcher",
            done_markers=["[final]"],
        )
        result = MultiAgentOrchestrator(reg, router, max_handoffs=4).run(
            "Find the key facts about renewable energy"
        )
        assert result.stop_reason == "completed"
        assert result.handoff_path() == "researcher -> writer"
        assert result.final_agent == "writer"
        assert "[final]" in result.final_response
        # Exactly one handoff, recorded with provenance.
        assert len(result.handoffs) == 1
        assert result.handoffs[0].from_agent == "researcher"
        assert result.handoffs[0].to_agent == "writer"

    def test_each_agent_runs_its_own_governed_pipeline(self):
        reg = _team()
        router = KeywordRouter(
            routes={"researcher": ["find", "facts about"], "writer": ["write", "draft"]},
            default="researcher",
            done_markers=["[final]"],
        )
        result = MultiAgentOrchestrator(reg, router).run(
            "Find the key facts about renewable energy"
        )
        # The researcher's turn actually executed its governed search tool.
        researcher_turn = result.turns[0]
        assert researcher_turn.agent_name == "researcher"
        assert researcher_turn.actions_executed == 1


class TestBounds:
    def test_max_handoffs_terminal(self):
        # Two agents that always point at each other -> unbounded without a cap.
        a = _agent("hand to b: write draft")
        b = _agent("hand to a: research find")
        reg = AgentRegistry()
        reg.register("a", a, "A")
        reg.register("b", b, "B")
        router = KeywordRouter(
            routes={"a": ["research", "find"], "b": ["write", "draft"]},
            default="a",
            done_markers=["__never__"],
        )
        result = MultiAgentOrchestrator(reg, router, max_handoffs=2).run("research this")
        assert result.stop_reason == "max_handoffs"
        # initial turn + max_handoffs additional turns
        assert len(result.turns) == 3

    def test_empty_registry_rejected(self):
        with pytest.raises(ValueError):
            MultiAgentOrchestrator(AgentRegistry(), KeywordRouter(routes={}))


class TestLLMRouter:
    def test_supervisor_routes_then_done(self):
        reg = _team()
        # Supervisor: start with researcher, then writer, then done.
        supervisor = SequentialMockAdapter(
            ["ROUTE: researcher", "ROUTE: writer", "DONE"]
        )
        router = LLMRouter(supervisor)
        result = MultiAgentOrchestrator(reg, router, max_handoffs=4).run(
            "Handle this request"
        )
        assert result.stop_reason == "completed"
        assert result.handoff_path() == "researcher -> writer"

    def test_router_unknown_agent_completes_gracefully(self):
        reg = _team()
        supervisor = SequentialMockAdapter(["ROUTE: ghost"])
        router = LLMRouter(supervisor)
        result = MultiAgentOrchestrator(reg, router).run("Handle this")
        # Unknown starting agent -> no turns, graceful completion.
        assert result.stop_reason in {"completed", "empty"}
        assert result.turns == []
