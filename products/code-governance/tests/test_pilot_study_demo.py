"""The MVP 1F offline study demo must run deterministically, keep supplied/synthetic
results out of live metrics, verify its evidence pack offline, honestly report
LIVE_PILOT_NOT_RUN + INSUFFICIENT_LIVE_EVIDENCE, and end with execution disabled."""
from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import pilot_study_demo  # noqa: E402


def test_offline_study_demo_runs():
    out = pilot_study_demo.run(verbose=False)
    # No live evaluations -> live distribution is empty and verdict is honest.
    assert sum(out["live_dist"].values()) == 0
    assert out["readiness"] == "INSUFFICIENT_LIVE_EVIDENCE"
    assert out["pack_ok"] is True
    assert out["evidence_status"] == "OFFLINE_VERIFIED"
    assert out["live_pilot"] == "LIVE_PILOT_NOT_RUN"
    assert out["exec"] == "DISABLED"


def test_offline_study_demo_deterministic():
    assert pilot_study_demo.run(verbose=False) == pilot_study_demo.run(verbose=False)
