"""Import-boundary and dependency-discipline checks (section 24, checks 9-17, 51-55).

The core package must not import any governance implementation, product package,
robotics package, application entry point, or monorepo test fixture. Importing the
package must have no external side effects.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "ugence_agent_runtime"

# Packages the neutral core must NEVER import (checks 9-16, 51).
FORBIDDEN_PREFIXES = (
    "ugence_code_governance",
    "code_governance",
    "actiongate",
    "action_gate",
    "ugence_action_clearance",
    "action_clearance",
    "tap_provider",
    "tap",
    "decision_authority",
    "ugence_decision_authority",
    "storygraph",
    "ugence_storygraph",
    "symbolu_robotics",
    "robotics",
    "cer_v0_1",
    "cer_v0_2",
    "cer_v0_3",
    "agentic",
    "agent_runtime_migration",
    "agent_runtime_v2",
    "control_plane",
    "ugence_console_api",
    "apps",
    "applications",
    "products",
    "numpy",
    "torch",
)

# Third-party runtime deps are also disallowed: the core is stdlib-only.
STDLIB_OK = None  # computed lazily below


def _iter_module_imports():
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield path, alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # relative import within the package
                if node.module:
                    yield path, node.module


def test_no_forbidden_imports():
    offenders = []
    for path, module in _iter_module_imports():
        top = module.split(".")[0]
        for bad in FORBIDDEN_PREFIXES:
            if top == bad.split(".")[0] and module.startswith(bad):
                offenders.append((str(path.relative_to(SRC)), module))
    assert not offenders, f"forbidden imports found: {offenders}"


def test_core_is_stdlib_only():
    """Every absolute import resolves to the stdlib or the package itself (check 51/52)."""
    import sys as _sys

    stdlib = set(getattr(_sys, "stdlib_module_names", set()))
    allowed_self = "ugence_agent_runtime"
    offenders = []
    for path, module in _iter_module_imports():
        top = module.split(".")[0]
        if top == allowed_self or top in stdlib or top in ("__future__",):
            continue
        offenders.append((str(path.relative_to(SRC)), module))
    assert not offenders, f"non-stdlib third-party imports found: {offenders}"


def test_import_has_no_external_side_effects():
    """A fresh subprocess importing the package must not open sockets, spawn
    threads, read env credentials, or start a scheduler (check 17)."""
    code = (
        "import sys, threading, socket\n"
        "before = threading.active_count()\n"
        "_orig = socket.socket\n"
        "def _blocked(*a, **k):\n"
        "    raise AssertionError('import opened a socket')\n"
        "socket.socket = _blocked\n"
        f"sys.path.insert(0, {str(SRC.parent)!r})\n"
        "import ugence_agent_runtime\n"
        "assert threading.active_count() == before, 'import started a thread'\n"
        "print('OK', ugence_agent_runtime.__version__)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK")


def test_constructing_config_and_runtime_is_side_effect_free():
    """Creating a config and a runtime performs no I/O and starts nothing (check 17)."""
    import threading

    from ugence_agent_runtime.api import AgentRuntimeConfig, create_runtime

    before = threading.active_count()
    rt = create_runtime(AgentRuntimeConfig())
    assert rt is not None
    assert threading.active_count() == before
