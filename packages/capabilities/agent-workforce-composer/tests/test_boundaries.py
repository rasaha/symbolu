"""Import-boundary + no-runtime tests (§24 — Boundaries; invariants I13, I14, I15)."""
from __future__ import annotations

import ast
import pathlib
import sys

import ugence_agent_workforce_composer  # noqa: F401
import ugence_agent_workforce_composer.api  # noqa: F401

_SRC = pathlib.Path(ugence_agent_workforce_composer.__file__).resolve().parent

# Prohibited top-level import roots (Phase 0 boundary contract §3).
_FORBIDDEN_ROOTS = {
    "agentic", "agent_runtime_v2", "agent_runtime_migration",
    "ugence_model_selection", "execution_gate", "ai_hiring",
    "ugence_procurement", "ugence_actiongate_provider", "ugence_action_clearance",
    "ugence_storygraph", "control_plane", "cloud_controller",
    "requests", "httpx", "urllib3", "socket", "aiohttp", "openai", "anthropic",
    "torch", "boto3",
}

# The compiler is a DATA-ONLY seam: AWC must not import it in core code either.
_FORBIDDEN_ROOTS.add("ugence_policy_workflow_compiler")


def _iter_py():
    for path in _SRC.rglob("*.py"):
        yield path


def test_no_forbidden_imports_in_source():
    offenders = []
    for path in _iter_py():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots = [n.name.split(".")[0] for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            for root in roots:
                if root in _FORBIDDEN_ROOTS:
                    offenders.append(f"{path.name}: imports {root}")
    assert not offenders, offenders


def test_importing_api_does_not_load_prohibited_modules():
    # Isolated subprocess: importing the public API must not pull in H16 / Agent
    # Runtime / Model Selection / the compiler / product packages. Run clean so a
    # sibling test (e.g. the compiler-reference test) cannot pollute sys.modules.
    import subprocess
    code = (
        "import ugence_agent_workforce_composer.api, sys;"
        "banned=['agentic','ugence_model_selection','ugence_policy_workflow_compiler',"
        "'ai_hiring','ugence_procurement','ugence_actiongate_provider','ugence_action_clearance'];"
        "hit=[b for b in banned if b in sys.modules];"
        "print('HIT:'+','.join(hit)); sys.exit(1 if hit else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code],
                            capture_output=True, text=True,
                            env={"PYTHONPATH": str(_SRC.parent)})
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_socket_or_network_symbols_used():
    text = "\n".join(p.read_text(encoding="utf-8") for p in _iter_py())
    for banned in ("socket.socket", "urllib.request", "http.client", "subprocess."):
        assert banned not in text


def test_no_system_clock_reads():
    # I13: logical time is injected; the core never reads the wall clock.
    text = "\n".join(p.read_text(encoding="utf-8") for p in _iter_py()
                     if p.name != "version.py")  # version.py may read package metadata only
    for banned in ("time.time(", "datetime.now(", "datetime.utcnow("):
        assert banned not in text


def test_leaf_dependency_footprint():
    # Only stdlib + pydantic may back the core modules.
    import ugence_agent_workforce_composer.eligibility as elig
    src = pathlib.Path(elig.__file__).read_text(encoding="utf-8")
    assert "import pydantic" not in src  # eligibility itself is pure stdlib + local
