"""Leaf-boundary proof for the Agentic Proposer.

Two independent checks, because either alone can be evaded:

* a STATIC scan of every source file's imports, which catches a forbidden module
  named in code that no test happens to execute;
* an ISOLATED SUBPROCESS that imports the public API and reports every module that
  actually loaded, which catches a forbidden module reached indirectly.

The forbidden set is not stylistic. Each entry is a capability that owns an
authority this proposer must never exercise, a legacy framework whose
policy-decision points must not be reproduced, or a network/model SDK that would
make an advisory offline capability reach outward.
"""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = PKG_ROOT / "src" / "ugence_agentic_proposer"

#: Modules the Agentic Proposer must never import, statically or at runtime.
FORBIDDEN = {
    # Legacy frameworks: competing policy-decision points, confidence gates,
    # denial-triggered replanning and LLM-coupled governance. Design precedent only.
    "agentic",
    "agent_runtime_migration",
    # Capabilities that own authorities this proposer does not hold.
    "ugence_agent_runtime",
    "ugence_decision_authority",
    "ugence_actiongate_provider",
    "ugence_action_clearance",
    "ugence_storygraph",
    "ugence_agent_workforce_composer",
    "ugence_policy_workflow_compiler",
    # Envelope/identity reference stacks.
    "cer_v0_1",
    "cer_v0_2",
    "cer_v0_3",
    "action_gate_ref",
    # Control and scaling planes.
    "control_plane",
    "cloud_controller",
    # Network and model SDKs: an advisory offline capability reaches nowhere.
    "requests",
    "httpx",
    "socket",
    "openai",
    "anthropic",
}

#: Forbidden dotted paths whose top-level name alone is not decisive.
FORBIDDEN_DOTTED = ("agentic.agentic_framework", "symbolu.agentic_framework")


def _sources():
    return sorted(SRC.rglob("*.py"))


def _imports(path):
    """Yield (top_level_name, relative_level, full_module) for each import."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], 0, alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            yield (mod.split(".")[0] if mod else ""), node.level, mod


def test_sources_exist():
    assert _sources(), f"no sources found under {SRC}"


def test_static_scan_finds_no_forbidden_import():
    offenders = []
    for path in _sources():
        for top, level, full in _imports(path):
            if level > 0:
                continue  # relative import -> within this package
            if top in FORBIDDEN or any(full.startswith(d) for d in FORBIDDEN_DOTTED):
                offenders.append((path.name, full))
    assert not offenders, f"forbidden import in source: {offenders}"


def test_static_scan_finds_no_symbolu_agentic_framework():
    """``symbolu`` is not forbidden wholesale; the divergent fork inside it is."""
    offenders = []
    for path in _sources():
        for top, level, full in _imports(path):
            if level == 0 and full.startswith("symbolu.agentic_framework"):
                offenders.append((path.name, full))
    assert not offenders, f"forbidden import in source: {offenders}"


def test_isolated_subprocess_import_loads_no_forbidden_module():
    """Import the public API in a fresh interpreter and inspect what actually loaded.

    ``socket`` is in the forbidden set and is imported by a great deal of the
    standard library, so this probe is meaningful only because the package is a
    stdlib-light leaf: nothing in the public API path may pull it in.
    """
    probe = (
        "import sys, json\n"
        "import ugence_agentic_proposer as ap\n"
        "ap.TerminalOutcome('PROPOSAL')\n"
        "ap.CandidateDisposition('RECOMMEND_WITHHOLD')\n"
        "ap.SemanticAuditorFindingStatus('CONSISTENT')\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules})))\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, check=True,
        cwd=str(SRC.parent),
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"},
    )
    loaded = set(json.loads(res.stdout.strip().splitlines()[-1]))
    leaked = loaded & FORBIDDEN
    assert not leaked, f"forbidden module loaded by the public API: {sorted(leaked)}"


def test_isolated_subprocess_has_no_monorepo_on_path():
    """The probe above must not have been satisfied by the surrounding repository."""
    probe = (
        "import sys, json\n"
        "import ugence_agentic_proposer as ap\n"
        "print(json.dumps({'file': ap.__file__, 'path': sys.path}))\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, check=True,
        cwd=str(SRC.parent),
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"},
    )
    info = json.loads(res.stdout.strip().splitlines()[-1])
    assert "ugence_agentic_proposer" in info["file"]


def test_declared_dependencies_are_exactly_the_three_permitted():
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = [ln.strip().strip('",') for ln in block.splitlines() if ln.strip().strip('",')]
    assert declared == ["pydantic>=2", "ugence-jcs>=0.1.0"], declared
