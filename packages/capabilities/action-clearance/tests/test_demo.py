"""The offline demonstration must run deterministically and end with no execution."""
from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import clearance_demo  # noqa: E402


def test_demo_runs():
    out = clearance_demo.run(verbose=False)
    assert out["clear"] == "CLEAR"
    assert out["clear_valid_until_bounded"] is True
    assert out["obligations_superset"] is True
    assert "parallelism:MAX=2" in out["effective_constraints"]  # narrowed
    assert out["missing"] == "HOLD"
    assert out["freeze"] == "HOLD"
    assert out["mismatch"] == "BLOCK"
    assert out["conflict"] == "ESCALATE"
    assert out["replay_identical_fingerprint"] is True
    assert out["persistence"] == "NONE"
    assert out["reservation"] == "NONE"
    assert out["execution"] == "DISABLED"


def test_demo_deterministic():
    assert clearance_demo.run(verbose=False) == clearance_demo.run(verbose=False)
