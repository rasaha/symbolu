"""
Runtime factory + stub-adapter substitution seam tests.

Pins the contract of ``build_cg_mcp_agent`` (see
``docs/RUNTIME_MCP_PATH.md``):

  1. Stub adapter + allow_stub=True -> silent composition, runnable agent.
  2. Stub adapter + allow_stub=False (default) -> emits a WARNING
     labelled as stub-usage.
  3. Non-stub adapter (no IS_STUB) -> silent composition, no warning.
  4. The factory wires AgenticLLMWrapper with the default mapping
     and a CGToolDispatcher backed by the adapter + gateway.
  5. Provenance markers on ``StubCGLLMAdapter`` are intact
     (``IS_STUB`` + ``STATE_PROVENANCE``) so any external audit
     consumer can detect stub signals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pytest

from agentic.agentic_framework.agent import AgenticLLMWrapper
from agentic.agentic_framework.cg_tool_dispatcher import (
    CGToolDispatcher,
    DEFAULT_ACTION_TYPE_TO_TOOL,
    build_cg_mcp_agent,
)
from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter
from agentic.agentic_framework.mcp_gateway import create_mock_mcp_gateway


class _FakeRealAdapter:
    """A non-stub CG-capable adapter stand-in. Satisfies the dispatcher
    protocol (``last_cg_metadata``) and the ``LLMClient`` protocol
    (``call(prompt) -> str``), but carries no ``IS_STUB`` marker —
    so the factory must treat it as a real adapter and stay silent."""

    def __init__(self) -> None:
        self.last_cg_metadata: Dict[str, Any] = {}

    def call(self, prompt: str) -> str:
        # Populate metadata to match the MistralCGAdapter contract.
        state = [0.0] * 32
        state[17] = 0.5
        state[22] = 0.6
        self.last_cg_metadata = {
            "state": state,
            "delta_S": [0.0] * 32,
            "delta_bhava": None,
            "intent_phase": None,
        }
        return "fake real response"


class TestStubProvenanceMarkers:
    """Gap 5 hardening: stub adapter is self-identifying."""

    def test_stub_is_stub_marker(self):
        assert StubCGLLMAdapter.IS_STUB is True

    def test_stub_state_provenance_tag(self):
        assert StubCGLLMAdapter.STATE_PROVENANCE == "deterministic_stub"

    def test_stub_populates_metadata_on_call(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        # Pre-call: attribute is unset (matches MistralCGAdapter's
        # "not generated yet" state — dispatcher treats both as
        # missing metadata via its empty-dict fallback).
        assert getattr(adapter, "last_cg_metadata", None) in (None, {})
        adapter.call("any prompt")
        assert "state" in adapter.last_cg_metadata
        assert len(adapter.last_cg_metadata["state"]) == 32


class TestBuildCgMcpAgentComposes:
    """Factory returns a fully wired AgenticLLMWrapper."""

    def test_returns_agentic_llm_wrapper(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        agent = build_cg_mcp_agent(adapter=adapter, allow_stub=True)
        assert isinstance(agent, AgenticLLMWrapper)

    def test_agent_has_dispatcher_and_default_mapping(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        agent = build_cg_mcp_agent(adapter=adapter, allow_stub=True)
        assert isinstance(agent.dispatcher, CGToolDispatcher)
        assert agent.dispatcher.adapter is adapter
        assert agent.action_type_to_tool == DEFAULT_ACTION_TYPE_TO_TOOL

    def test_custom_mapping_overrides_default(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        custom = {"search": "custom_search"}
        agent = build_cg_mcp_agent(
            adapter=adapter,
            allow_stub=True,
            action_type_to_tool=custom,
        )
        assert agent.action_type_to_tool == custom

    def test_custom_gateway_instance_used_as_given(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        gateway = create_mock_mcp_gateway()
        agent = build_cg_mcp_agent(
            adapter=adapter, gateway=gateway, allow_stub=True,
        )
        assert agent.dispatcher.gateway is gateway

    def test_gateway_factory_called_when_no_gateway(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        sentinel_gateway = create_mock_mcp_gateway()
        call_count = {"n": 0}

        def _factory():
            call_count["n"] += 1
            return sentinel_gateway

        agent = build_cg_mcp_agent(
            adapter=adapter,
            gateway_factory=_factory,
            allow_stub=True,
        )
        assert call_count["n"] == 1
        assert agent.dispatcher.gateway is sentinel_gateway

    def test_agent_kwargs_forwarded(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        agent = build_cg_mcp_agent(
            adapter=adapter,
            allow_stub=True,
            use_llm_for_decomposition=False,
            memory_window=7,
        )
        assert agent.use_llm_for_decomposition is False
        assert agent.memory_window == 7

    def test_tier_flows_into_dispatcher(self):
        adapter = StubCGLLMAdapter(default_response="ok")
        agent = build_cg_mcp_agent(
            adapter=adapter, allow_stub=True, tier="enterprise",
        )
        assert agent.dispatcher.tier == "enterprise"


class TestBuildCgMcpAgentStubWarning:
    """Stub-adapter guardrail: warns unless ``allow_stub=True``."""

    def test_stub_without_allow_stub_logs_warning(self, caplog):
        adapter = StubCGLLMAdapter(default_response="ok")
        with caplog.at_level(
            logging.WARNING,
            logger="agentic.agentic_framework.cg_tool_dispatcher",
        ):
            build_cg_mcp_agent(adapter=adapter)
        # Warning must mention stub + be actionable.
        assert any(
            "STUB adapter" in rec.message for rec in caplog.records
        ), caplog.records
        assert any(
            "allow_stub=True" in rec.message for rec in caplog.records
        )

    def test_stub_with_allow_stub_is_silent(self, caplog):
        adapter = StubCGLLMAdapter(default_response="ok")
        with caplog.at_level(
            logging.WARNING,
            logger="agentic.agentic_framework.cg_tool_dispatcher",
        ):
            build_cg_mcp_agent(adapter=adapter, allow_stub=True)
        assert not any(
            "STUB adapter" in rec.message for rec in caplog.records
        )

    def test_non_stub_adapter_never_warns(self, caplog):
        adapter = _FakeRealAdapter()
        with caplog.at_level(
            logging.WARNING,
            logger="agentic.agentic_framework.cg_tool_dispatcher",
        ):
            agent = build_cg_mcp_agent(adapter=adapter)  # no allow_stub
        assert not any(
            "STUB adapter" in rec.message for rec in caplog.records
        )
        # Sanity: composition still succeeded.
        assert isinstance(agent, AgenticLLMWrapper)


class TestBuildCgMcpAgentSubstitutionParity:
    """Swapping stub -> non-stub adapter changes NOTHING else."""

    def test_stub_and_real_produce_identical_wiring_shape(self):
        stub = StubCGLLMAdapter(default_response="ok")
        real = _FakeRealAdapter()

        stub_agent = build_cg_mcp_agent(adapter=stub, allow_stub=True)
        real_agent = build_cg_mcp_agent(adapter=real)

        # Same type, same mapping, same dispatcher class, same tier.
        assert type(stub_agent) is type(real_agent)
        assert stub_agent.action_type_to_tool == real_agent.action_type_to_tool
        assert type(stub_agent.dispatcher) is type(real_agent.dispatcher)
        assert stub_agent.dispatcher.tier == real_agent.dispatcher.tier


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
