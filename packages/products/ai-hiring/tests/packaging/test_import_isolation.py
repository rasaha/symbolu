"""Import-isolation tests — the package resolves without the monorepo.

These assert the canonical package imports cleanly with no dependence on the
current working directory, no monorepo path injection, and no repo-root shim.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys


def test_import_does_not_depend_on_cwd(tmp_path):
    """Importing from an unrelated working directory still works.

    The subprocess is given the parent's *absolute* import roots (so this holds
    whether the package is pip-installed or on a source path), and is run from an
    unrelated directory. The variable under test is the working directory, not the
    import roots — a genuine cwd-dependence would still fail here.
    """
    env = dict(os.environ)
    # Absolute import roots only — a relative entry would defeat the cwd test.
    roots = [p for p in sys.path if p and os.path.isabs(p) and os.path.isdir(p)]
    env["PYTHONPATH"] = os.pathsep.join(roots)
    code = (
        "import ugence_ai_hiring as u;"
        "p = u.build_in_memory_platform();"
        "assert type(p).__name__ == 'HiringPlatform';"
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_no_repo_root_shim_modules_loaded():
    """The legacy repo-root compat namespaces must not be what we resolve."""
    import ugence_ai_hiring  # noqa: F401

    # If any of these are present, they must be the CANONICAL installed packages,
    # never a repo-root shim. The core never imports the legacy names at all.
    for legacy in ("decision_governance", "governance_providers"):
        assert legacy not in sys.modules, (
            f"core import pulled in legacy shim {legacy!r}"
        )


def test_canonical_kernel_is_importable():
    """The audited Ugence dependencies resolve by their canonical names."""
    for mod in (
        "ugence_decision_authority",
        "ugence_governance_provider_framework",
        "ugence_governance_contracts",
    ):
        importlib.import_module(mod)
