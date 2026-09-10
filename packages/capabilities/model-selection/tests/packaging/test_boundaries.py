"""Model Selection is a leaf capability, and the tests say so mechanically.

Its ``pyproject.toml`` declares no runtime dependency and its README calls it a leaf that
"imports no application, domain, control-plane, orchestrator, Hybrid LLM, Governance
Provider Framework, provider, pilot, experiment, or benchmark code". Until now that was
prose. A leaf whose leafness is only asserted in a README stops being a leaf the first
time someone adds a convenient import.

The source scan is the primary gate; the isolated-subprocess probe is the backstop that
catches a forbidden module reached indirectly, whatever spelled it.
"""

from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "ugence_model_selection"

#: Everything this package's own docstrings and README swear it does not reach.
FORBIDDEN_ROOTS = frozenset({
    "agentic", "ai_hiring", "applications", "domains", "experiments", "symbolu",
    "trading", "trading2", "cyber_security", "robotics_reliability_bench",
    "control_plane", "cloud_controller", "cloud_scaling_operations",
    "ugence_agent_runtime", "ugence_console_api", "ugence_governance_contracts",
    "ugence_governance_provider_framework", "ugence_storygraph", "ugence_action_clearance",
    "ugence_decision_authority", "risk_authority", "benchmarks", "eval",
    "model_selection_pilot", "model_selection_experiment", "governed_inference_pilot",
})

#: A leaf with no declared dependency may import no third party at all.
ALLOWED_THIRD_PARTY: frozenset[str] = frozenset()


def _module_files():
    return sorted(SRC.rglob("*.py"))


def _imported_roots(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:      # level > 0 is a relative import
                yield node.module.split(".")[0]


def test_the_scan_actually_sees_the_package():
    """A boundary test that scanned nothing would pass forever."""
    files = _module_files()
    assert len(files) >= 9, [f.name for f in files]
    assert {f.name for f in files} >= {
        "gate.py", "policy.py", "authority.py", "registry.py", "states.py", "api.py"}


@pytest.mark.parametrize("module", _module_files(), ids=lambda p: p.name)
def test_no_module_imports_a_forbidden_root(module):
    for root in _imported_roots(module):
        assert root not in FORBIDDEN_ROOTS, f"{module.name} imports {root}"


def test_the_package_imports_nothing_outside_the_standard_library():
    """`dependencies = []` is a promise; this is the check on it."""
    stdlib = set(sys.stdlib_module_names)
    for module in _module_files():
        for root in _imported_roots(module):
            if root == "ugence_model_selection":
                continue
            assert root in stdlib or root in ALLOWED_THIRD_PARTY, \
                f"{module.name} imports non-stdlib {root}"


def test_importing_the_package_in_isolation_pulls_in_no_forbidden_module():
    """The backstop: what the source scan cannot see because it was reached indirectly.

    Run in a subprocess with only ``src`` on the path, so the repository root — which
    this package's own conftest adds for the legacy-namespace cross-checks — cannot make
    a forbidden module importable by accident.
    """
    probe = (
        "import sys, json\n"
        "import ugence_model_selection.api as api\n"
        "api.ExecutionGate(); api.GateConfig()\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules})))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, check=True,
        cwd=str(ROOT / "src"),
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src"),
             "PYTHONHASHSEED": "0"},
    )
    loaded = set(json.loads(result.stdout))
    assert not (loaded & FORBIDDEN_ROOTS), sorted(loaded & FORBIDDEN_ROOTS)


def test_the_package_reads_no_system_clock():
    """``now`` is always passed in, so every decision replays.

    ``states.py`` says so in its module docstring; this is what holds it to it.
    """
    offenders = []
    for module in _module_files():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"time", "now", "utcnow"}:
                value = node.value
                if isinstance(value, ast.Name) and value.id in {"time", "datetime"}:
                    offenders.append(f"{module.name}:{node.lineno}")
    assert not offenders, offenders
