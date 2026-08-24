"""Leaf-boundary proof for the Agentic Proposer.

**What the invariant is (OD-2).** The Agentic Proposer must not possess or exercise
networking authority. That is a statement about what this package does, not about
which standard-library modules happen to be resident in the interpreter. An approved
runtime dependency loading a stdlib module while constructing its own schemas is not
this package reaching outward.

This distinction is forced by a fact, not chosen for convenience: `pydantic` is a
ratified core dependency, and *defining any* ``BaseModel`` loads ``socket`` through
pydantic-core's schema build. Bare ``import pydantic`` does not. So the moment the
first contract model exists, a whole-process ``sys.modules`` assertion fails for a
reason that has nothing to do with this package's authority.

Enforcement is therefore layered, and no layer is load-bearing alone:

1. a STATIC scan of every production source file's imports, which catches a forbidden
   module named in code no test happens to execute;
2. an extension of that scan to aliases, ``from`` imports, module-qualified use and
   the ordinary dynamic-import spellings, so the rule is not defeated by spelling;
3. an ISOLATED SUBPROCESS that first establishes the approved dependency baseline —
   import pydantic, define a minimal model — and then imports this package, asserting
   it introduces **no additional** forbidden roots beyond that baseline;
4. the declared-dependency allowlist, so this exemption can never authorize a new
   networking library;
5. negative controls proving a direct ``socket`` import or use in this package still
   fails, even though pydantic's transitive load is permitted.

**The enforcement ceiling, stated honestly.** Layers 1 and 2 read source text and an
AST. They catch every declared import, alias, ``from`` import, module-qualified use
and literal dynamic import. They do **not** catch a module name assembled at runtime
from parts, read from a file, an environment variable or a data structure — the same
disclosed limitation ``test_no_local_canonicalization.py`` records for the identity
substrate. Layer 3 compares module sets and so catches an indirect load whatever
spelled it, but only for what the probe's import path actually executes. Nothing here
proves the impossibility of every dynamically assembled import. **The invariant
remains architectural and review-enforced; these guards are defence-in-depth, not a
proof.**

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

import pytest

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

#: Dynamic-import entry points. A literal module name passed to one of these is an
#: import, and is read as one.
DYNAMIC_IMPORT_CALLS = ("import_module", "__import__")

#: Ratified runtime dependencies whose own internal imports are not this package's
#: conduct. Pinned by equality against the declared dependency set below, so this
#: cannot become a hiding place for a new library.
DEPENDENCY_BASELINE_MODULES = ("pydantic",)


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


def _dynamic_imports(tree):
    """Literal module names passed to ``import_module`` or ``__import__``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        called = (func.id if isinstance(func, ast.Name)
                  else func.attr if isinstance(func, ast.Attribute) else "")
        if called not in DYNAMIC_IMPORT_CALLS:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            yield first.value


def _qualified_uses(tree):
    """Attribute access rooted at a forbidden top-level name — ``socket.socket()``.

    An unimported root cannot be used, so the import scan already covers the ordinary
    case; this catches the spelling where the import is added and the scan is read as
    covering only the import statement.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in FORBIDDEN:
            yield root.id


def _forbidden_reaches(path):
    """Every way ``path`` reaches a forbidden root: import, alias, from, dynamic, use."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for top, level, full in _imports(path):
        if level > 0:
            continue
        if top in FORBIDDEN or any(full.startswith(d) for d in FORBIDDEN_DOTTED):
            found.append(("import", full))
    for name in _dynamic_imports(tree):
        if name.split(".")[0] in FORBIDDEN or any(
                name.startswith(d) for d in FORBIDDEN_DOTTED):
            found.append(("dynamic-import", name))
    for name in _qualified_uses(tree):
        found.append(("qualified-use", name))
    return found


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


def test_static_scan_finds_no_aliased_dynamic_or_qualified_reach():
    """Layer 2. The same rule, spelled the other four ways."""
    offenders = []
    for path in _sources():
        for how, what in _forbidden_reaches(path):
            offenders.append((path.name, how, what))
    assert not offenders, f"forbidden reach in source: {offenders}"


@pytest.mark.parametrize("sample,expected", [
    ("import socket\n", "import"),
    ("import socket as s\n", "import"),
    ("from socket import socket\n", "import"),
    ("from socket import *\n", "import"),
    ("import importlib\nimportlib.import_module('socket')\n", "dynamic-import"),
    ("__import__('socket')\n", "dynamic-import"),
    ("import socket\nsocket.socket()\n", "qualified-use"),
    ("import socket\ns = socket.AF_INET\n", "qualified-use"),
])
def test_the_reach_scanner_sees_every_spelling(tmp_path, sample, expected):
    """Negative controls for layers 1-2 (OD-2 clause 5). Each spelling must be seen,
    whatever pydantic is permitted to load."""
    probe = tmp_path / "probe.py"
    probe.write_text(sample, encoding="utf-8")
    hows = {how for how, _ in _forbidden_reaches(probe)}
    assert expected in hows, f"{sample!r} was not caught: saw {hows}"


@pytest.mark.parametrize("sample", [
    "import pydantic\nclass M(pydantic.BaseModel):\n    a: str\n",
    "from pydantic import BaseModel\nclass M(BaseModel):\n    a: str\n",
    "import datetime\nimport enum\n",
])
def test_the_reach_scanner_permits_the_ratified_dependency(tmp_path, sample):
    """The exemption is real: defining a pydantic model is not a forbidden reach,
    even though doing so loads ``socket`` inside pydantic."""
    probe = tmp_path / "probe.py"
    probe.write_text(sample, encoding="utf-8")
    assert _forbidden_reaches(probe) == []


def test_static_scan_finds_no_symbolu_agentic_framework():
    """``symbolu`` is not forbidden wholesale; the divergent fork inside it is."""
    offenders = []
    for path in _sources():
        for top, level, full in _imports(path):
            if level == 0 and full.startswith("symbolu.agentic_framework"):
                offenders.append((path.name, full))
    assert not offenders, f"forbidden import in source: {offenders}"


#: The approved baseline: import each ratified dependency and exercise the part of it
#: that loads the most — for pydantic, defining a model, which is what triggers
#: pydantic-core's schema build.
_BASELINE_SETUP = (
    "import pydantic\n"
    "class _Baseline(pydantic.BaseModel):\n"
    "    a: str\n"
)
_REPORT = "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules})))\n"


def _module_roots(body):
    """Module roots resident after running ``body`` in a fresh interpreter."""
    res = subprocess.run(
        [sys.executable, "-c", "import sys, json\n" + body + _REPORT],
        capture_output=True, text=True, check=True,
        cwd=str(SRC.parent),
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0",
             "PYTHONPATH": str(SRC.parent)},
    )
    return set(json.loads(res.stdout.strip().splitlines()[-1]))


def test_the_dependency_baseline_is_what_it_claims_to_be():
    """The premise of the layered rule, demonstrated rather than assumed: pydantic
    alone loads ``socket``, and it does so when a model is DEFINED, not on import."""
    bare = _module_roots("import pydantic\n")
    with_model = _module_roots(_BASELINE_SETUP)
    assert "socket" not in bare, (
        "bare `import pydantic` now loads socket; the baseline's justification has "
        "changed and OD-2 should be re-read")
    assert "socket" in with_model, (
        "defining a pydantic model no longer loads socket; the exemption may no "
        "longer be needed and should be removed rather than kept")


def test_isolated_subprocess_adds_no_forbidden_module_beyond_the_baseline():
    """Layer 3, per OD-2. Establish the approved dependency baseline first, then
    import this package and assert it introduces no ADDITIONAL forbidden root.

    This replaces the whole-process assertion. It still catches a forbidden module
    reached indirectly — whatever spelled it — but attributes to this package only
    what this package actually adds.
    """
    baseline = _module_roots(_BASELINE_SETUP)
    after = _module_roots(
        _BASELINE_SETUP
        + "import ugence_agentic_proposer as ap\n"
        "ap.TerminalOutcome('PROPOSAL')\n"
        "ap.CandidateDisposition('RECOMMEND_WITHHOLD')\n"
        "ap.SemanticAuditorFindingStatus('CONSISTENT')\n"
    )
    introduced = (after - baseline) & FORBIDDEN
    assert not introduced, (
        f"the public API introduced forbidden modules beyond the ratified "
        f"dependency baseline: {sorted(introduced)}")


def test_layer_three_alone_cannot_see_a_direct_import_which_is_why_it_is_not_alone():
    """Negative control for layer 3 (OD-2 clause 5), and an honest statement of its
    ceiling: once ``socket`` is in the baseline, a module importing it directly adds
    nothing to ``sys.modules``. The differential cannot see it. Layers 1-2 must, and
    do — which is why the enforcement is layered rather than replaced."""
    baseline = _module_roots(_BASELINE_SETUP)
    after = _module_roots(_BASELINE_SETUP + "import socket\n")
    assert "socket" in baseline, "precondition: pydantic's load is in the baseline"
    assert (after - baseline) & FORBIDDEN == set(), (
        "precondition: a direct import is invisible to the differential")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        probe = pathlib.Path(d) / "probe.py"
        probe.write_text("import socket\n", encoding="utf-8")
        assert _forbidden_reaches(probe), (
            "layers 1-2 must catch what layer 3 structurally cannot")


def test_the_baseline_modules_are_exactly_the_ratified_dependencies():
    """Layer 4. The exemption covers the ratified dependencies and nothing else, so it
    cannot become a hiding place for a networking library."""
    assert DEPENDENCY_BASELINE_MODULES == ("pydantic",)
    assert set(DEPENDENCY_BASELINE_MODULES) & FORBIDDEN == set()



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
    assert declared == ["pydantic>=2", "ugence-jcs>=0.2.0"], declared
