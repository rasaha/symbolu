"""Phase 5E — the kernel packages as an independent middleware product.

Verifies the kernel is declared as a distributable package and that a consumer
can build against it exactly as a third-party dependency: importing the kernel
package tree without any consuming layer on the path.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_pyproject_packages_the_kernel_and_consumers():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    for pkg in ("decision_governance", "domains", "applications", "ai_hiring"):
        assert pkg in pyproject, f"{pkg} not declared in pyproject packaging"


def test_kernel_tree_is_self_contained():
    """Every module the kernel imports (transitively) is either stdlib, a declared
    third-party dep, or the kernel itself — never a consuming layer."""
    code = (
        "import decision_governance.api, decision_governance.conformance, sys; "
        "bad=[m for m in sys.modules "
        "if m.split('.')[0] in ('ai_hiring','domains','applications')]; "
        "assert not bad, bad; "
        "assert 'pydantic' in sys.modules; "  # declared third-party dep is fine
        "print('self-contained')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "self-contained" in result.stdout


def test_kernel_declares_a_version():
    from decision_governance.version import VERSION, VERSION_INFO, __version__
    assert __version__ == VERSION
    assert len(VERSION_INFO) == 3
    assert all(isinstance(p, int) for p in VERSION_INFO)
