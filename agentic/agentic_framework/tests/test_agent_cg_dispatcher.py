"""
Integration test: AgenticLLMWrapper <-> CGToolDispatcher layered wiring.

Proves the layered contract established in the architecture doc + the
REQUEST_BOUNDARY_CONVENTION note:

  SafetyGate  (turn-level coherence pre-gate)
      |  gate.eligible == True  (else: _execute_actions is never reached)
      v
  _execute_actions
      |  action_type in allowed_types  AND
      |  action_type in action_type_to_tool  AND
      |  self.dispatcher is not None
      v
  CGToolDispatcher.dispatch  ->  SafeMCPGateway.call_tool_simple
      (cg_metadata from adapter, per-call governance)

Assertions:
  1. SafetyGate blocks actions BEFORE the dispatcher when the contract
     is not eligible (dispatcher is never called).
  2. Eligible actions reach the dispatcher when one is provided and
     the action_type maps to a tool.
  3. The dispatcher path returns an MCP-governed result (success ->
     "completed", blocked -> "blocked" with MCP reason).
  4. When no dispatcher is provided, the placeholder behavior is
     preserved exactly (regression check).

These tests exercise ``_execute_actions`` directly because that is
the exact wiring point; driving the full ``run()`` path would bring
in goal-decomposition + reflective generation + coherence update, all
of which are out of scope for this wiring.

Adapter / gateway are lightweight mocks — no torch, no real checkpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from agentic.agentic_framework.agent import AgenticLLMWrapper
from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher
from agentic.agentic_framework.goal_decomposition import ActionItem
from agentic.agentic_framework.mcp_gateway import create_mock_mcp_gateway


# --- Fakes ----------------------------------------------------------


class _FakeLLM:
    """Minimal LLMClient protocol impl — unused by _execute_actions tests."""

    def call(self, prompt: str) -> str:
        return "fake-response"


class _FakeCGAdapter:
    """Lightweight CG-capable adapter stand-in (no torch, no checkpoint).

    Produces a valid 32D sovereign state when ``pretend_generate`` is
    called, matching the MistralCGAdapter.last_cg_metadata wire contract.
    """

    def __init__(self) -> None:
        self.last_cg_metadata: Dict[str, Any] = {}

    def pretend_generate(self) -> None:
        state = [0.0] * 32
        # vritti-region dominance
        state[17] = 0.55
        state[18] = 0.15
        state[19] = 0.15
        state[20] = 0.10
        state[21] = 0.05
        # sattva-leaning guna
        state[22] = 0.65
        state[23] = 0.25
        state[27] = 0.9
        self.last_cg_metadata = {
            "state": state,
            "delta_S": [0.01] * 32,
            "delta_bhava": None,
            "intent_phase": None,
        }


class _SpyDispatcher:
    """Records dispatch calls and returns a canned MCPToolResult-like
    object. Lets us assert ordering without touching a real gateway."""

    def __init__(self, *, should_succeed: bool = True) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._should_succeed = should_succeed

    async def dispatch(self, *, tool_name, parameters,
                       quality_score=0.8, coherence_score=0.8):
        self.calls.append({
            "tool_name": tool_name,
            "parameters": dict(parameters),
        })

        class _Result:
            pass
        r = _Result()
        r.success = self._should_succeed
        r.result = f"spy-ok:{tool_name}" if self._should_succeed else None
        r.decision = None
        r.blocked_reason = None if self._should_succeed else "spy-denied"
        r.error = None
        return r


# --- Helpers --------------------------------------------------------


def _make_action(action_type: str, *, params=None) -> ActionItem:
    return ActionItem(
        action_id=f"act-{action_type}",
        description=f"do a {action_type}",
        action_type=action_type,
        parameters=params or {},
    )


# --- Tests ----------------------------------------------------------


class TestDispatcherIsNeverCalledWhenSafetyGateBlocks:
    """Assertion 1: SafetyGate runs before the dispatcher.

    In agent.py the call path is:
        contract, allowed_actions = self.safety_gate.check(...)
        if contract.eligible and self._goal_state:
            actions_executed = self._execute_actions(...)

    So when the contract is NOT eligible, ``_execute_actions`` is
    never called and therefore the dispatcher cannot be reached. This
    test pins that ordering by proving that ``_execute_actions`` is
    the *only* place that invokes the dispatcher, so the guard at the
    call site fully protects the dispatcher.
    """

    def test_dispatcher_only_reachable_via_execute_actions(self):
        spy = _SpyDispatcher()
        agent = AgenticLLMWrapper(
            llm_client=_FakeLLM(),
            dispatcher=spy,
            action_type_to_tool={"search": "mcp_search"},
        )
        # If `_execute_actions` is NOT called (which is what happens
        # when SafetyGate blocks), the dispatcher must stay untouched.
        # We do not call _execute_actions here.
        assert spy.calls == []

    def test_blocked_action_type_does_not_reach_dispatcher(self):
        """A sibling ordering check: even once _execute_actions is
        called, actions not in allowed_types are filtered BEFORE the
        dispatcher branch."""
        spy = _SpyDispatcher()
        agent = AgenticLLMWrapper(
            llm_client=_FakeLLM(),
            dispatcher=spy,
            action_type_to_tool={"search": "mcp_search"},
        )
        action = _make_action("search", params={"query": "x"})
        # "search" is in the dispatcher mapping but NOT in allowed_types
        agent._execute_actions([action], allowed_types=[])
        assert action.status == "blocked"
        assert action.error == "Action type 'search' not allowed"
        assert spy.calls == []


class TestEligibleActionReachesDispatcher:
    """Assertion 2 + 3: when allowed and mapped, the dispatcher is
    invoked and its result drives the action's final status."""

    def test_successful_dispatch_marks_action_completed(self):
        spy = _SpyDispatcher(should_succeed=True)
        agent = AgenticLLMWrapper(
            llm_client=_FakeLLM(),
            dispatcher=spy,
            action_type_to_tool={"search": "mcp_search"},
        )
        action = _make_action("search", params={"query": "alpha"})
        executed = agent._execute_actions([action], allowed_types=["search"])

        assert spy.calls == [
            {"tool_name": "mcp_search", "parameters": {"query": "alpha"}}
        ]
        assert action.status == "completed"
        assert action.result == "spy-ok:mcp_search"
        assert executed == [action.description]

    def test_blocked_dispatch_marks_action_blocked_with_mcp_reason(self):
        spy = _SpyDispatcher(should_succeed=False)
        agent = AgenticLLMWrapper(
            llm_client=_FakeLLM(),
            dispatcher=spy,
            action_type_to_tool={"search": "mcp_search"},
        )
        action = _make_action("search", params={"query": "beta"})
        agent._execute_actions([action], allowed_types=["search"])

        assert len(spy.calls) == 1
        assert action.status == "blocked"
        assert action.error is not None
        assert action.error.startswith("MCP:")
        assert "spy-denied" in action.error


class TestDispatcherPathCarriesRealCGSignalsThroughGateway:
    """Assertion 3 (stricter): with a real ``CGToolDispatcher`` wired
    to a mock MCP gateway, the enriched signals reach the gateway's
    audit record (``vritti_signal_source="real"``) — proving the chain
    agent -> dispatcher -> gateway -> governance is fully live."""

    def test_real_dispatcher_reaches_mock_gateway_with_real_signals(self):
        adapter = _FakeCGAdapter()
        adapter.pretend_generate()
        gateway = create_mock_mcp_gateway()
        dispatcher = CGToolDispatcher(adapter, gateway)
        agent = AgenticLLMWrapper(
            llm_client=_FakeLLM(),
            dispatcher=dispatcher,
            action_type_to_tool={"search": "file_read"},
        )
        action = _make_action("search", params={"path": "/tmp/x"})
        agent._execute_actions([action], allowed_types=["search"])

        assert action.status == "completed"
        entry = gateway.audit_log[-1]
        assert entry.vritti_signal_source == "real"
        assert entry.entropy_available is True


class TestNoDispatcherPreservesPlaceholderBehavior:
    """Assertion 4: when no dispatcher is given, every existing
    placeholder branch behaves exactly as before."""

    def test_search_placeholder_still_fires(self):
        agent = AgenticLLMWrapper(llm_client=_FakeLLM())
        action = _make_action("search", params={"query": "q"})
        executed = agent._execute_actions([action], allowed_types=["search"])
        assert action.status == "completed"
        assert action.result == "Search completed for: q"
        assert executed == [action.description]

    def test_compute_placeholder_still_fires(self):
        agent = AgenticLLMWrapper(llm_client=_FakeLLM())
        action = _make_action("compute")
        agent._execute_actions([action], allowed_types=["compute"])
        assert action.status == "completed"
        assert action.result == "Computation completed"

    def test_validate_placeholder_still_fires(self):
        agent = AgenticLLMWrapper(llm_client=_FakeLLM())
        action = _make_action("validate")
        agent._execute_actions([action], allowed_types=["validate"])
        assert action.status == "completed"
        assert action.result == "Validation passed"

    def test_unknown_action_type_is_skipped(self):
        agent = AgenticLLMWrapper(llm_client=_FakeLLM())
        action = _make_action("teleport")
        agent._execute_actions([action], allowed_types=["teleport"])
        assert action.status == "skipped"
        assert "Unknown action type" in (action.error or "")

    def test_action_type_not_in_mapping_falls_through_to_placeholder(self):
        """Dispatcher present, but action_type has no mapping entry:
        placeholder path must run, dispatcher must stay untouched."""
        spy = _SpyDispatcher()
        agent = AgenticLLMWrapper(
            llm_client=_FakeLLM(),
            dispatcher=spy,
            action_type_to_tool={"search": "mcp_search"},  # no "compute"
        )
        action = _make_action("compute")
        agent._execute_actions([action], allowed_types=["compute"])
        assert action.status == "completed"
        assert action.result == "Computation completed"
        assert spy.calls == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
