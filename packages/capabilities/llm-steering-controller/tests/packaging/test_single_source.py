"""The canonical routing controller exists in exactly one place."""

from __future__ import annotations

import os
import subprocess
import sys

_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                       "scripts", "audit_single_source.py"))


def test_single_source_audit_passes():
    r = subprocess.run([sys.executable, _SCRIPT], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SINGLE SOURCE OK" in r.stderr
