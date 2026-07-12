"""Shared builders for MCP integration tests."""

from __future__ import annotations

import importlib.util
import pathlib
import tempfile

from action_gateway_mcp import ClientSession, McpGateway
from action_gateway_mcp._core import FixedClock, ref_evidence

START = "2026-07-12T14:00:00.000Z"


def make():
    clock = FixedClock(START)
    mcp = McpGateway(sandbox_root=tempfile.mkdtemp(prefix="mcp-test-"), clock=clock)
    return mcp, ClientSession(clock=clock)


def backup(mcp, action_hash):
    return ref_evidence.build_evidence(
        bound_to=action_hash, producer="restore-checker", generated_at=mcp.clock.now(),
        valid_until=mcp.clock.plus(3600), evidence_version="1",
        kind="verified_restorable_backup", fidelity_or_confidence="HIGH",
        content={"backup_id": "b1", "restore_tested": True})


def approved_terraform(mcp, cs, workspace="w"):
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": workspace})
    mcp.evaluate(cs.context(), p["request_id"])
    mcp.simulate(cs.context(), p["request_id"])
    return p


def load_scenarios():
    """Load the MCP demo scenarios by explicit path (avoids the top-level
    ``demos`` package-name collision with the sibling runtime gateway)."""
    path = pathlib.Path(__file__).resolve().parents[1] / "demos" / "scenarios.py"
    spec = importlib.util.spec_from_file_location("mcp_demo_scenarios", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
