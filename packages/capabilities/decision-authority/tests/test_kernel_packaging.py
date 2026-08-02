"""The canonical Decision Authority package ships as an independent capability.

Verifies the canonical package ``ugence_decision_authority`` (distribution
``ugence-decision-authority``) is declared as a self-contained distributable and
that a consumer can build against it exactly as a third-party dependency —
importing the kernel tree with only the canonical ``src`` on the path.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
CANON_SRC = PKG_ROOT / "src"


def test_pyproject_declares_the_canonical_package():
    pyproject = (PKG_ROOT / "pyproject.toml").read_text()
    assert 'name = "ugence-decision-authority"' in pyproject
    assert 'include = ["ugence_decision_authority*"]' in pyproject
    assert 'where = ["src"]' in pyproject
    # Bounded capability: depends only on pydantic; no consuming layer or other capability.
    assert "pydantic" in pyproject
    for forbidden in ("ai_hiring", "domains", "applications", "governance_providers",
                      "actiongate", "storygraph", "tap_provider"):
        assert forbidden not in pyproject


def test_kernel_tree_is_self_contained():
    """Every module the kernel imports (transitively) is stdlib, a declared
    third-party dep (pydantic), or the kernel itself — never a consuming layer."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CANON_SRC)
    code = (
        "import ugence_decision_authority.api, ugence_decision_authority.conformance, sys; "
        "bad=[m for m in sys.modules "
        "if m.split('.')[0] in ('ai_hiring','domains','applications')]; "
        "assert not bad, bad; "
        "assert 'pydantic' in sys.modules; "
        "print('self-contained')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert "self-contained" in result.stdout


def test_kernel_declares_a_version():
    from ugence_decision_authority.version import VERSION, VERSION_INFO, __version__
    assert __version__ == VERSION == "1.0.0"
    assert len(VERSION_INFO) == 3
    assert all(isinstance(p, int) for p in VERSION_INFO)
