"""The MVP 1C offline durable demo must run deterministically, prove restart-safe
recovery + integrity-verified reconstruction, and end with execution disabled."""
from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import durable_shadow_demo  # noqa: E402


def test_demo_runs():
    out = durable_shadow_demo.run(verbose=False)
    assert out["records"] > 0 and out["events"] > 0
    assert out["recovery"] == "RECOVERED_COMPLETE"
    assert out["reconstruction"] == "COMPLETE"
    assert out["bundle_ok"] is True
    assert out["stale"] == "STALE"
    assert out["tamper"] == "INTEGRITY_FAILURE"
    assert out["exec"] == "DISABLED"
    assert out["reservation"] == "NONE"
    assert out["persistence"] == "DURABLE_SHADOW_REFERENCE"


def test_demo_structural_outcome_is_deterministic():
    a = durable_shadow_demo.run(verbose=False)
    b = durable_shadow_demo.run(verbose=False)
    # The audit bundle re-verifies every run. Note: the *bundle_fingerprint*
    # itself is NOT stable across full pipelines, because the upstream
    # Decision-Authority-minted CER carries a wall-clock issued_at/content_hash
    # (the documented MVP 1B provenance caveat) that flows into the chain. So we
    # assert the deterministic structural outcome, not the wall-clock-derived
    # fingerprint. Record/envelope/bundle determinism over *fixed* inputs is
    # proven directly in test_durable_persistence.py.
    for key in ("records", "events", "recovery", "reconstruction", "bundle_ok",
                "stale", "tamper", "exec", "persistence", "reservation"):
        assert a[key] == b[key], key
