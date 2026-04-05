"""
Smoke test for examples/cg_tool_demo.py.

This test pins the end-to-end enrichment path as exercised by the
demo script: DemoCGAdapter → last_cg_metadata → call_tool_simple
→ governance audit with real sovereign signals.

The demo is the first (and currently only) honest full-path exerciser
of the Phase 1 + Phase 2 wiring. This test ensures it stays runnable
and stays correct as the enrichment seam evolves.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest


def _run_async(coro):
    """Run ``coro`` on a fresh event loop without touching the global
    default loop (avoids conflicts with sibling tests that use
    ``asyncio.get_event_loop().run_until_complete(...)``)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _load_demo_module():
    """Load examples/cg_tool_demo.py as a module without requiring
    examples/ to be a package."""
    repo_root = Path(__file__).resolve().parents[3]
    demo_path = repo_root / "examples" / "cg_tool_demo.py"
    assert demo_path.is_file(), f"demo script missing at {demo_path}"
    spec = importlib.util.spec_from_file_location(
        "cg_tool_demo", demo_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["cg_tool_demo"] = module
    spec.loader.exec_module(module)
    return module


class TestCGToolDemoSmoke:
    """The demo must stay runnable and stay correct."""

    def test_demo_module_loads(self):
        """examples/cg_tool_demo.py imports cleanly."""
        mod = _load_demo_module()
        assert hasattr(mod, "DemoCGAdapter")
        assert hasattr(mod, "run_demo")
        assert hasattr(mod, "main")

    def test_demo_adapter_produces_cg_metadata_shape(self):
        """DemoCGAdapter.generate() populates last_cg_metadata with the
        same wire shape as MistralCGAdapter: 32-float state + delta_S."""
        mod = _load_demo_module()
        adapter = mod.DemoCGAdapter()
        assert adapter.last_cg_metadata == {}

        adapter.generate("test prompt")
        md = adapter.last_cg_metadata
        assert set(md.keys()) == {"state", "delta_S", "delta_bhava", "intent_phase"}
        assert isinstance(md["state"], list)
        assert len(md["state"]) == 32
        assert all(isinstance(x, float) for x in md["state"])
        assert md["delta_S"] is not None
        assert len(md["delta_S"]) == 32

    def test_demo_adapter_state_varies_with_prompt(self):
        """Different prompts produce different sovereign states (as a
        real adapter would)."""
        mod = _load_demo_module()
        a1, a2 = mod.DemoCGAdapter(), mod.DemoCGAdapter()
        a1.generate("short")
        a2.generate("a much longer prompt that should shift the state")
        assert a1.last_cg_metadata["state"] != a2.last_cg_metadata["state"]

    def test_demo_end_to_end_enrichment_path(self):
        """Running the demo end-to-end drives real sovereign signals
        through the governance audit path."""
        mod = _load_demo_module()
        # Run the full demo coroutine. Any failure in the enrichment
        # seam, bridge helpers, or gateway wiring would raise here.
        _run_async(mod.run_demo())

    def test_demo_produces_real_signal_audit_entry(self):
        """Reproduce the demo flow directly and assert on the audit
        record fields the demo itself prints."""
        from agentic.agentic_framework.mcp_gateway import (
            create_mock_mcp_gateway,
        )
        mod = _load_demo_module()
        adapter = mod.DemoCGAdapter()
        adapter.generate("What file should I inspect?")

        gateway = create_mock_mcp_gateway()
        result = _run_async(gateway.call_tool_simple(
            tool_name="file_read",
            parameters={"path": "/tmp/demo.txt"},
            quality_score=0.9,
            coherence_score=0.9,
            cg_metadata=adapter.last_cg_metadata,
            tier="consumer",
        ))
        assert result.success is True

        entry = gateway.audit_log[-1]
        # This is the demo's core claim: CG metadata produced REAL
        # sovereign signals that governance actually consumed.
        assert entry.vritti_signal_source == "real"
        assert entry.entropy_available is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
