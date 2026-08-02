"""The offline reference demonstration must run deterministically and end disabled."""
from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import shadow_demo  # noqa: E402


def test_demo_runs_and_reaches_shadow_complete():
    out = shadow_demo.run(verbose=False)
    # partial pass fails closed
    assert out["partial_proceed"] is False
    assert out["partial_state"] == "CLAIMS_INCOMPLETE"
    # complete pass proceeds and reconstructs
    assert out["complete_proceed"] is True
    assert out["final_state"] == "SHADOW_COMPLETE"
    assert out["reconstruction"] == "COMPLETE"
    # execution disabled
    assert out["execution_status"] == "DISABLED"
    # head invalidation
    assert out["new_revision_differs"] is True
    assert out["old_evidence_stale"] is True
    assert out["old_chain_state"] == "STALE"


def test_demo_is_deterministic():
    assert shadow_demo.run(verbose=False) == shadow_demo.run(verbose=False)
