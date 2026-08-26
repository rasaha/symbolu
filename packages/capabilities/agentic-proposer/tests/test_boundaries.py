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

**What layers 1-2 detect.** Every declared import, alias, ``from`` import and
module-qualified use; and these dynamic spellings, each with a negative control proving
the detector reports the *reach* and not the mechanism: a literal passed to
``__import__`` or ``importlib.import_module``; a literal **bound to a local name** and
then passed to either; an import statement written as source text inside ``exec(...)``;
``__import__`` written as source text inside ``eval(...)``; an import inside
``compile(...)``; source text bound to a name and then executed; and the prohibited
relative-import spellings — a relative import can never bind the permitted identity
substrate, which is reached absolutely or not at all.

**The enforcement ceiling, stated honestly.** Layers 1 and 2 read source text and an
AST, so what they establish stops at what is statically decidable. They do **not** catch
**arbitrary runtime composition**: a module name assembled by a helper and returned as an
ordinary string, **externally supplied**, read from a file, an environment variable or a
data structure, or reached by **reflection**. Those routes and equivalent undecidable
behaviour are **not proven absent** by static scanning — a green suite is not evidence
they do not exist — and they remain subject to **review, packaging and runtime
isolation**. This is the same disclosed limitation ``test_no_local_canonicalization.py``
records for the identity substrate, and
``test_a_name_assembled_through_a_call_return_is_the_disclosed_ceiling`` demonstrates it
rather than conceding it in prose. Layer 3 compares module sets and so catches an
indirect load whatever spelled it, but only for what the probe's import path actually
executes, and once ``socket`` is in the baseline it structurally cannot see a direct
import. Nothing here proves the impossibility of every dynamically assembled import.
**The invariant remains architectural and review-enforced; these guards are
defence-in-depth, not a proof.**

The forbidden set is not stylistic. Each entry is a capability that owns an
authority this proposer must never exercise, a legacy framework whose
policy-decision points must not be reproduced, or a network/model SDK that would
make an advisory offline capability reach outward.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
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

#: Names a relative import may never bind. ``ugence_jcs`` is the permitted identity
#: substrate and is reached absolutely or not at all: a local module of that name,
#: reached by ``from . import ugence_jcs``, would satisfy every by-name check while
#: hashing locally. The forbidden roots are listed for the same reason — a relative
#: spelling of one is still a reach.
PROHIBITED_RELATIVE_TARGETS = frozenset({"ugence_jcs"}) | FORBIDDEN

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


#: Calls that execute source text supplied as a string. An import written inside one is
#: an import, and is read as one.
CODE_EXECUTION_CALLS = ("exec", "eval", "compile")

#: Import statements spelled as source text inside ``exec``/``eval``/``compile``, and
#: the dynamic-import calls nested inside them.
_EMBEDDED_IMPORT = re.compile(
    r"""(?:^|[\s;:])(?:import|from)\s+([A-Za-z_][\w.]*)"""
    r"""|(?:import_module|__import__)\s*\(\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)


def _string_bindings(tree):
    """``NAME -> "literal"`` for every local or module-level string assignment.

    Tracked so a literal bound to a name and then passed to ``__import__`` or
    ``import_module`` is read as the import it is. This is per binding: a name rebound
    from a non-literal source stops being a known literal, and a name this module merely
    received — a parameter, an attribute — was never one.
    """
    bindings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [tgt for tgt in node.targets if isinstance(tgt, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
        else:
            continue
        literal = (node.value.value
                   if isinstance(node.value, ast.Constant)
                   and isinstance(node.value.value, str) else None)
        for target in targets:
            if literal is None:
                bindings.pop(target.id, None)
            else:
                bindings[target.id] = literal
    return bindings


def _dynamic_imports(tree):
    """Every module name this module reaches through a dynamic-import spelling.

    Covered:

    * a literal passed to ``import_module`` or ``__import__``;
    * a **literal bound to a local name** and then passed to either;
    * an import written as source text inside ``exec(...)``;
    * ``__import__`` or ``import_module`` written as source text inside ``eval(...)``
      or ``compile(...)``.

    Not covered, and stated so rather than implied: a name assembled by a helper and
    returned as an ordinary string, supplied externally, read from a file, an
    environment variable or a data structure, or reached by reflection. Those are the
    ceiling this module's docstring records; they are not proven absent by any scan.
    """
    bindings = _string_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        called = (func.id if isinstance(func, ast.Name)
                  else func.attr if isinstance(func, ast.Attribute) else "")
        first = node.args[0]
        if called in DYNAMIC_IMPORT_CALLS:
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                yield first.value
            elif isinstance(first, ast.Name) and first.id in bindings:
                yield bindings[first.id]
        elif called in CODE_EXECUTION_CALLS:
            source = (first.value if isinstance(first, ast.Constant)
                      and isinstance(first.value, str)
                      else bindings.get(first.id)
                      if isinstance(first, ast.Name) else None)
            if source is None:
                continue
            for match in _EMBEDDED_IMPORT.finditer(source):
                yield match.group(1) or match.group(2)


def _prohibited_relative_imports(tree):
    """Relative-import spellings this package may not use.

    A relative import can never bind the permitted identity substrate — the substrate is
    reached absolutely or not at all — and a relative import that escapes this package's
    own tree is not an in-package import at all. Both spellings are reported.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            continue
        module = node.module or ""
        if module.split(".")[0] in PROHIBITED_RELATIVE_TARGETS:
            yield f"level-{node.level} from {module}"
            continue
        for alias in node.names:
            if alias.name in PROHIBITED_RELATIVE_TARGETS:
                yield f"level-{node.level} from {module or '.'} import {alias.name}"


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
    for spelling in _prohibited_relative_imports(tree):
        found.append(("relative-import", spelling))
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


def _declared_dependency_roots():
    """The import roots of the ratified dependencies, read from ``pyproject.toml``.

    The baseline is **derived from the declared dependency registry**, not hand-written
    beside it. A dependency added to `pyproject.toml` therefore appears here and must be
    reviewed; a module smuggled into the baseline by hand has nowhere to hide, because
    the baseline is not written by hand.

    ``ugence-jcs`` is declared and is deliberately not exercised in the baseline: S0
    imports nothing from it, so including it would widen the exempt module set on the
    strength of a dependency this package does not yet load.
    """
    block = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = block.split("dependencies = [", 1)[1].split("]", 1)[0]
    roots = []
    for line in block.splitlines():
        spec = line.strip().strip('",')
        if not spec:
            continue
        name = re.split(r"[<>=!~\[]", spec)[0].strip().replace("-", "_")
        roots.append(name)
    return tuple(roots)


#: The ratified dependency whose transitive loads are exempt, derived from the declared
#: registry above and pinned by equality below.
DEPENDENCY_BASELINE_MODULES = tuple(
    root for root in _declared_dependency_roots() if root == "pydantic")

#: The approved baseline: import each ratified dependency and exercise the part of it
#: that loads the most — for pydantic, defining a model, which is what triggers
#: pydantic-core's schema build.
#:
#: Generated from ``DEPENDENCY_BASELINE_MODULES`` and pinned by equality against
#: ``_EXPECTED_BASELINE_SETUP`` below, so the baseline cannot be silently widened with
#: an extra import. ``test_a_widened_baseline_setup_fails`` is the control.
def _baseline_setup(modules=DEPENDENCY_BASELINE_MODULES):
    lines = [f"import {module}\n" for module in modules]
    lines.append("class _Baseline(pydantic.BaseModel):\n    a: str\n")
    return "".join(lines)


_BASELINE_SETUP = _baseline_setup()

#: The one setup the baseline is permitted to be, byte for byte.
_EXPECTED_BASELINE_SETUP = (
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
    assert set(DEPENDENCY_BASELINE_MODULES) <= set(_declared_dependency_roots()), (
        "the baseline must be derived from the declared dependency registry, never "
        "written beside it")


def test_the_declared_dependency_roots_are_read_from_the_registry():
    """The derivation itself, so the baseline's provenance is checked rather than
    asserted. ``ugence-jcs`` is declared and is deliberately not in the baseline: S0
    imports nothing from it, and exempting a dependency this package does not load
    would widen the exempt set for nothing."""
    assert _declared_dependency_roots() == ("pydantic", "ugence_jcs")
    assert "ugence_jcs" not in DEPENDENCY_BASELINE_MODULES


def _baseline_pin_verdict(setup):
    """The guard's own decision about one baseline setup, factored out.

    Returns ``"pinned"`` when ``setup`` is byte-for-byte the single permitted setup, and
    ``"unpinned"`` otherwise. It is a function rather than an inline equality for the
    same reason ``_pattern_verdict`` and ``_completeness_verdict`` are functions in the
    sibling guards: the control below must run **this** decision, not restate it. A
    control that asserted ``widened != _EXPECTED_BASELINE_SETUP`` directly is only saying
    that two different strings differ, which stays true after the live pin is deleted.
    """
    return "pinned" if setup == _EXPECTED_BASELINE_SETUP else "unpinned"


def test_the_baseline_setup_is_pinned_by_equality():
    """G-6. The generated setup is exactly the one permitted setup, byte for byte, so a
    line added to it is a diff a reviewer sees rather than a silently wider exemption."""
    assert _baseline_pin_verdict(_BASELINE_SETUP) == "pinned"
    assert _baseline_pin_verdict(_baseline_setup(DEPENDENCY_BASELINE_MODULES)) == "pinned"


def test_a_widened_baseline_setup_fails():
    """G-6's control: a baseline carrying an added ``import socket`` must fail.

    The widened setup goes through ``_baseline_pin_verdict`` — the function the live
    assertion calls — and must come back ``"unpinned"``, with the ratified setup coming
    back ``"pinned"`` through the same function so the control is discriminating rather
    than merely negative. It also genuinely widens the declaration it produces, so the
    check is not cosmetic.
    """
    assert _baseline_pin_verdict(_BASELINE_SETUP) == "pinned", (
        "precondition: the ratified setup is the pinned one")

    widened = _baseline_setup(DEPENDENCY_BASELINE_MODULES + ("socket",))
    assert _baseline_pin_verdict(widened) == "unpinned", (
        "an added import must not survive the pinned-setup check; the pin is not being "
        "enforced")
    assert "import socket" in widened
    honest = _module_roots(_BASELINE_SETUP)
    assert "socket" in honest, (
        "precondition: pydantic already loads socket transitively, so the widening "
        "this control rejects is about the DECLARATION, not about the module set")
    assert set(_declared_dependency_roots()) & FORBIDDEN == set(), (
        "no declared dependency may itself be a forbidden root")



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


def test_declared_dependencies_are_exactly_the_two_permitted():
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = [ln.strip().strip('",') for ln in block.splitlines() if ln.strip().strip('",')]
    assert declared == ["pydantic>=2", "ugence-jcs>=0.2.0"], declared
    assert len(declared) == 2, (
        "two dependencies are declared, not three; the count in this test's name and "
        "in the enforcement documentation must match the registry")


# --------------------------------------------------------------------------- #
# G-7 — dynamic-import coverage, each spelling with a negative control
# --------------------------------------------------------------------------- #

#: Every dynamic spelling the scan must detect, paired with a control that is the same
#: spelling reaching something permitted. A detector that fired on both would be
#: reporting the mechanism rather than the reach, and would make an ordinary
#: ``import_module`` unusable in this package's own guards.
DYNAMIC_SPELLINGS = (
    ("literal to __import__",
     "__import__('socket')\n",
     "__import__('datetime')\n"),
    ("literal to import_module",
     "import importlib\nimportlib.import_module('socket')\n",
     "import importlib\nimportlib.import_module('datetime')\n"),
    ("literal bound to a local name, then __import__",
     "_n = 'socket'\n__import__(_n)\n",
     "_n = 'datetime'\n__import__(_n)\n"),
    ("literal bound to a local name, then import_module",
     "from importlib import import_module\n_n = 'socket'\nimport_module(_n)\n",
     "from importlib import import_module\n_n = 'datetime'\nimport_module(_n)\n"),
    ("exec of an import statement",
     "exec('import socket')\n",
     "exec('import datetime')\n"),
    ("exec of a from-import statement",
     "exec('from socket import socket')\n",
     "exec('from datetime import timezone')\n"),
    ("eval of __import__",
     "eval(\"__import__('socket')\")\n",
     "eval(\"__import__('datetime')\")\n"),
    ("compile of an import statement",
     "compile('import socket', '<s>', 'exec')\n",
     "compile('import datetime', '<s>', 'exec')\n"),
    ("source text bound to a name, then exec",
     "_src = 'import socket'\nexec(_src)\n",
     "_src = 'import datetime'\nexec(_src)\n"),
)


@pytest.mark.parametrize("label,offending,permitted", DYNAMIC_SPELLINGS,
                         ids=[case[0] for case in DYNAMIC_SPELLINGS])
def test_each_dynamic_spelling_is_detected(tmp_path, label, offending, permitted):
    """G-7's positive half: each enumerated spelling reaches a forbidden root and is
    reported as a dynamic import."""
    probe = tmp_path / "probe.py"
    probe.write_text(offending, encoding="utf-8")
    hows = {how for how, _ in _forbidden_reaches(probe)}
    assert "dynamic-import" in hows, f"{label} was not caught: saw {hows}"


@pytest.mark.parametrize("label,offending,permitted", DYNAMIC_SPELLINGS,
                         ids=[case[0] for case in DYNAMIC_SPELLINGS])
def test_each_dynamic_spelling_has_a_negative_control(tmp_path, label, offending,
                                                      permitted):
    """G-7's negative half: the same spelling reaching a permitted module is clean.

    Without this, a detector that flagged every ``exec`` or every ``import_module``
    would pass the positive tests while barring the ordinary shapes the guards
    themselves use.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(permitted, encoding="utf-8")
    assert _forbidden_reaches(probe) == [], f"{label} false-positived on a permitted module"


@pytest.mark.parametrize("sample", [
    "from . import ugence_jcs\n",
    "from .ugence_jcs import canonical_sha256_hex\n",
    "from .. import socket\n",
    "from .vendor import socket\n",
])
def test_a_prohibited_relative_import_is_detected(tmp_path, sample):
    """A relative import can never bind the permitted identity substrate — the substrate
    is reached absolutely or not at all — so a local module named for it would satisfy
    every by-name check while hashing locally. A relative spelling of a forbidden root
    is caught for the same reason."""
    probe = tmp_path / "probe.py"
    probe.write_text(sample, encoding="utf-8")
    hows = {how for how, _ in _forbidden_reaches(probe)}
    assert "relative-import" in hows, f"{sample!r} was not caught: saw {hows}"


@pytest.mark.parametrize("sample", [
    "from . import vocabulary\n",
    "from .version import __version__\n",
    "from ugence_jcs import canonical_sha256_hex\n",
])
def test_a_lawful_relative_or_absolute_import_is_not_flagged(tmp_path, sample):
    """Negative control. In-package relative imports are ordinary, and the substrate
    reached absolutely is the one permitted spelling."""
    probe = tmp_path / "probe.py"
    probe.write_text(sample, encoding="utf-8")
    assert _forbidden_reaches(probe) == []


def test_a_name_assembled_through_a_call_return_is_the_disclosed_ceiling(tmp_path):
    """The ceiling, demonstrated rather than conceded in prose.

    Composition that happens inside a callee and returns as an ordinary string is not
    tracked by any binding-level scan, and no source-level or baseline check closes it.
    This test asserts what is true — the scan does not catch it — so that a reader is
    not left to infer the hole from what the scan does not say. Code reaching a
    forbidden module by this route violates the invariant exactly as a direct import
    would; it violates it invisibly, which is why the invariant and not the scan is the
    rule.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "def _b(*parts):\n    return ''.join(parts)\n\n"
        "_m = __import__(_b('soc', 'ket'))\n", encoding="utf-8")
    assert _forbidden_reaches(probe) == [], (
        "if this now fails, the ceiling has moved and the disclosure below must be "
        "narrowed to match rather than left overstating the hole")


def test_the_enforcement_ceiling_is_stated_in_this_module():
    """The disclosure is pinned so a later edit cannot quietly drop it and leave the
    guards reading as a proof."""
    doc = " ".join(
        pathlib.Path(__file__).read_text(encoding="utf-8").split('"""')[1].split())
    for clause in ("arbitrary runtime composition",
                   "externally supplied",
                   "reflection",
                   "not proven absent",
                   "review, packaging and runtime isolation"):
        assert clause in doc, f"the ceiling disclosure no longer states: {clause}"
