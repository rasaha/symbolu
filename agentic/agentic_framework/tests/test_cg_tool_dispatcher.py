"""
Tests for CGToolDispatcher — the owner component that holds a
CG-capable adapter + SafeMCPGateway and composes them.

The dispatcher is tiny (single method) so the tests pin its
contract directly:

  1. When the adapter has CG metadata, it reaches governance as
     REAL sovereign signals (vritti_signal_source="real",
     entropy_available=True).
  2. When the adapter has NOT generated yet (empty last_cg_metadata),
     the call still succeeds and takes the fallback/no-CG path
     (matching the pre-Phase-1 behavior exactly).
  3. Tier is passed through.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher
from agentic.agentic_framework.mcp_gateway import create_mock_mcp_gateway


def _run_async(coro):
    """Run ``coro`` on a fresh event loop (see test_cg_tool_demo)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeCGAdapter:
    """Minimal stand-in matching the _CGCapableAdapter protocol."""

    def __init__(self) -> None:
        self.last_cg_metadata: Dict[str, Any] = {}

    def pretend_generate(self) -> None:
        """Populate a 32D sovereign state with the same wire shape as
        MistralCGAdapter / DemoCGAdapter."""
        state = [0.0] * 32
        # vritti-region dominance (indices 17..21)
        state[17] = 0.55
        state[18] = 0.15
        state[19] = 0.15
        state[20] = 0.10
        state[21] = 0.05
        # sattva-leaning guna (22..27)
        state[22] = 0.65
        state[23] = 0.25
        state[27] = 0.9
        self.last_cg_metadata = {
            "state": state,
            "delta_S": [0.01] * 32,
            "delta_bhava": None,
            "intent_phase": None,
        }


class TestCGToolDispatcher:
    def test_dispatches_with_cg_metadata_when_adapter_has_generated(self):
        """When the adapter holds CG metadata, the gateway receives it
        and governance consumes REAL sovereign signals."""
        adapter = _FakeCGAdapter()
        adapter.pretend_generate()
        gateway = create_mock_mcp_gateway()
        dispatcher = CGToolDispatcher(adapter, gateway)

        result = _run_async(dispatcher.dispatch(
            tool_name="file_read",
            parameters={"path": "/tmp/x.txt"},
        ))
        assert result.success is True

        entry = gateway.audit_log[-1]
        assert entry.vritti_signal_source == "real"
        assert entry.entropy_available is True

    def test_dispatches_without_cg_metadata_when_adapter_not_generated(self):
        """Empty last_cg_metadata → gateway receives cg_metadata=None
        and the audit shows the fallback/no-CG path."""
        adapter = _FakeCGAdapter()  # last_cg_metadata = {}
        gateway = create_mock_mcp_gateway()
        dispatcher = CGToolDispatcher(adapter, gateway)

        result = _run_async(dispatcher.dispatch(
            tool_name="file_read",
            parameters={"path": "/tmp/x.txt"},
        ))
        assert result.success is True

        entry = gateway.audit_log[-1]
        # No real sovereign signals reached governance.
        assert entry.vritti_signal_source != "real"
        assert entry.entropy_available is False

    def test_tier_is_passed_through(self):
        """The dispatcher forwards its configured tier to the gateway."""
        adapter = _FakeCGAdapter()
        adapter.pretend_generate()

        captured: Dict[str, Any] = {}

        class _CapturingGateway:
            async def call_tool_simple(self, **kwargs):
                captured.update(kwargs)
                class _R:
                    success = True
                return _R()

        dispatcher = CGToolDispatcher(
            adapter, _CapturingGateway(), tier="enterprise",
        )
        _run_async(dispatcher.dispatch(
            tool_name="search", parameters={"q": "x"},
        ))
        assert captured["tier"] == "enterprise"
        assert captured["cg_metadata"] is adapter.last_cg_metadata

    def test_dispatcher_reads_latest_metadata_every_call(self):
        """Each dispatch reads the adapter's CURRENT last_cg_metadata,
        not a cached snapshot from construction time."""
        adapter = _FakeCGAdapter()
        gateway = create_mock_mcp_gateway()
        dispatcher = CGToolDispatcher(adapter, gateway)

        # First call: no metadata yet → fallback path.
        _run_async(dispatcher.dispatch(
            tool_name="file_read", parameters={"path": "/tmp/a"},
        ))
        assert gateway.audit_log[-1].vritti_signal_source != "real"

        # Adapter generates. Next dispatch must see the new metadata.
        adapter.pretend_generate()
        _run_async(dispatcher.dispatch(
            tool_name="file_read", parameters={"path": "/tmp/b"},
        ))
        assert gateway.audit_log[-1].vritti_signal_source == "real"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
