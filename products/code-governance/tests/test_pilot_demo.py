"""The MVP 1D offline pilot demo must run deterministically, keep credentials out
of the durable store, verify its report offline, and end with execution disabled.

Also holds the *optional* live read-only GitHub smoke collection, which is skipped
by default and only runs when an explicit environment flag + allowlist + externally
supplied read-only credentials are present.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import pilot_shadow_demo  # noqa: E402


def test_offline_demo_runs():
    out = pilot_shadow_demo.run(verbose=False)
    assert out["clear"] == "CLEAR"
    assert "SOURCE_UNAVAILABLE" in out["timeout_failures"]
    assert out["stale"] is True
    assert out["conflicts"] == ["ACTIVE_INCIDENT"]
    assert out["report_ok"] is True
    assert out["credential_leaked"] is False
    assert out["exec"] == "DISABLED"


def test_offline_demo_deterministic():
    assert pilot_shadow_demo.run(verbose=False) == pilot_shadow_demo.run(verbose=False)


# --- optional live read-only GitHub smoke (skipped by default) --------------
_LIVE = os.environ.get("CG_PILOT_LIVE_GITHUB") == "1"


@pytest.mark.skipif(not _LIVE, reason="live GitHub read-only smoke is opt-in "
                                      "(set CG_PILOT_LIVE_GITHUB=1 + allowlist + creds)")
def test_live_github_readonly_smoke():  # pragma: no cover - opt-in, not run in CI
    # This test is intentionally excluded from ordinary CI. It performs GET-only
    # requests, prints no credential data, makes no mutations, and only reads an
    # allowlisted repository/PR using externally supplied read-only credentials.
    repo = os.environ.get("CG_PILOT_LIVE_REPO", "")
    assert repo, "CG_PILOT_LIVE_REPO must be set for the live smoke"
    pytest.skip("live smoke requires an external read-only transport implementation")
