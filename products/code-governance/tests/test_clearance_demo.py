"""The MVP 1B offline demo must run deterministically and end with execution disabled."""
from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import clearance_shadow_demo  # noqa: E402


def test_demo_runs():
    out = clearance_shadow_demo.run(verbose=False)
    assert out["clear"] == "CLEAR" and out["clear_human"] is False
    assert out["hold"] == "HOLD" and out["hold_human"] is False
    assert out["block"] == "BLOCK" and out["block_human"] is False
    assert out["escalate"] == "ESCALATE" and out["escalate_human"] is True
    assert "INCIDENT_COMMANDER" in out["escalate_authorities"]
    assert out["old_chain_stale"] == "STALE"
    assert out["replay_identical"] is True
    assert out["exec"] == "DISABLED"
    assert out["reservation"] == "NONE"
    assert out["persistence"] == "SHADOW_REFERENCE_ONLY"


def test_demo_deterministic():
    assert clearance_shadow_demo.run(verbose=False) == clearance_shadow_demo.run(verbose=False)
