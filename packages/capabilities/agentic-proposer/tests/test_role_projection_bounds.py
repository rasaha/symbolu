"""D8's containment bounds on the D1 role projection, enforced mechanically.

The Agent Constitution does not exist and will not exist before S1 (D8). The D1
``CognitiveRoleContract`` therefore proceeds as a proposer-local **v0** projection,
bounded to: never exported to shared contracts, carrying no constitution-derived
attribute, exposing no role lifecycle verb. The ADR records two of those bounds as
an ``[R]`` obligation on S1 — the export bound and the lifecycle-verb bound — and
this module discharges it.

Both bounds are enforceable now, before the projection exists, and both are
enforced over the repository rather than over prose:

* the EXPORT bound is checked from the shared-contract side. Every shared contract
  distribution in this repository is discovered and scanned for a role-projection
  name, for a re-export of it, and for a dependency on this capability. That check
  is meaningful today: it would fail the moment a projection name appeared there,
  whether or not this package ever defines one.
* the LIFECYCLE bound is checked over this package's whole defined surface —
  modules, classes, methods and annotated fields — so a verb cannot arrive on a
  projection later without failing here.

Scanners are self-tested against synthetic sources below.
"""
from __future__ import annotations

import ast
import enum
import re
import importlib
import pathlib
import pkgutil

import pytest

import ugence_agentic_proposer as ap

SRC = pathlib.Path(ap.__file__).resolve().parent
PKG_ROOT = SRC.parents[1]
REPO_ROOT = PKG_ROOT.parents[2]
PACKAGES = REPO_ROOT / "packages"

#: This distribution, as a shared contract package would have to name it to depend on it.
THIS_DISTRIBUTION = "ugence-agentic-proposer"
THIS_NAMESPACE = "ugence_agentic_proposer"
#: Any name carrying the projection. Matched as a substring so a renamed or wrapped
#: re-export (``CognitiveRoleContractV0``, ``CognitiveRoleRef``) is caught too.
PROJECTION_MARKERS = ("CognitiveRole", "COGNITIVE_ROLE", "cognitive_role")
#: Verbs that would make this capability an author of roles rather than a reader of
#: them. D1 and D3 both depend on their absence: activation state is an input fact,
#: never computed, and no identity or role is minted, changed or ended here.
#: Matched as stems, so an inflected form ("activation", "ratified", "revoking")
#: does not slip past a scan looking for the infinitive.
LIFECYCLE_VERBS = (
    "mint", "activat", "deactivat", "reactivat", "suspend", "unsuspend",
    "ratif", "revok", "reinstat", "issu", "expir", "provision", "grant",
    "assign_role", "authoriz", "enroll", "replac",
)


def _distribution_name(pyproject):
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name =") or stripped.startswith("name="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _shared_contract_packages():
    """Every distribution in this repository whose role is to hold shared contracts.

    Discovered, not listed, so a shared contract package added later is covered
    without anyone remembering to add it here.
    """
    found = []
    for pyproject in sorted(PACKAGES.rglob("pyproject.toml")):
        if any(part in {"build", "dist", ".venv", "node_modules"} for part in pyproject.parts):
            continue
        name = _distribution_name(pyproject)
        if "contract" in name and name != THIS_DISTRIBUTION:
            found.append((name, pyproject.parent))
    return found


def _defined_names(source, filename="<sample>"):
    """Every NAME a module defines or re-exports: classes, functions, assignments,
    class-level fields and methods, imported bindings, and the strings listed in
    ``__all__``.

    Strings elsewhere — docstrings, enum VALUES — are deliberately excluded. A term
    in a docstring is not a name on the surface, and the ratified D4 values are
    already governed by ``test_vocabulary.py``; scanning them here would confuse a
    vocabulary question with a lifecycle one.
    """
    tree = ast.parse(source, filename=filename)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                names |= {e.value for e in ast.walk(node.value)
                          if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        elif isinstance(node, ast.ImportFrom):
            names |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            names |= {a.asname or a.name.split(".")[0] for a in node.names}
    return names


def _projection_hits(names):
    """Every name in ``names`` that carries the role projection."""
    return sorted(n for n in names if any(m in n for m in PROJECTION_MARKERS))


def _snapshot_projection_hits(body):
    """Markers present in a public-API snapshot's text."""
    return sorted(m for m in PROJECTION_MARKERS if m in body)


def _capability_dependency_hits(text):
    """References to this distribution or its namespace in another package's text."""
    return sorted(m for m in (THIS_DISTRIBUTION, THIS_NAMESPACE) if m in text)


def _lifecycle_offenders(names):
    return sorted(n for n in names
                  if any(verb in n.lower() for verb in LIFECYCLE_VERBS))


# --------------------------------------------------------------------------- #
# Scanner self-tests
# --------------------------------------------------------------------------- #

def test_the_name_scanner_sees_a_re_export():
    names = _defined_names(
        "from ugence_agentic_proposer import CognitiveRoleContract\n"
        "__all__ = ['CognitiveRoleContract']\n")
    assert any(marker in n for n in names for marker in PROJECTION_MARKERS)


def test_the_name_scanner_sees_class_level_fields_and_methods():
    names = _defined_names(
        "class RoleProjection:\n"
        "    role_ref: str\n"
        "    def activate(self):\n        ...\n")
    assert {"RoleProjection", "role_ref", "activate"} <= names


@pytest.mark.parametrize("sample", [
    "def mint_role():\n    ...\n",
    "class R:\n    def suspend(self):\n        ...\n",
    "class R:\n    activation_ratified: bool\n",
    "def revoke_role_binding():\n    ...\n",
])
def test_the_verb_scanner_flags_a_lifecycle_verb(sample):
    assert _lifecycle_offenders(_defined_names(sample))


@pytest.mark.parametrize("sample", [
    "class R:\n    role_ref: str\n    is_active: bool\n",
    "def read_role(role):\n    return role.role_ref\n",
])
def test_the_verb_scanner_permits_reading_an_input_fact(sample):
    """``is_active`` supplied as an input fact is lawful; computing it is not."""
    assert not _lifecycle_offenders(_defined_names(sample))


def test_the_name_scanner_sees_a_bare_re_export():
    """Without ``__all__``. The re-export self-test above is satisfied through the
    ``__all__`` path, so a broken ImportFrom branch would survive it."""
    names = _defined_names("from ugence_agentic_proposer import CognitiveRoleContract\n")
    assert "CognitiveRoleContract" in names
    names = _defined_names(
        "from ugence_agentic_proposer import CognitiveRoleContract as RoleRef\n")
    assert "RoleRef" in names


@pytest.mark.parametrize("names,expected", [
    ({"CognitiveRoleContract"}, ["CognitiveRoleContract"]),
    ({"CognitiveRoleContractV0", "Unrelated"}, ["CognitiveRoleContractV0"]),
    ({"COGNITIVE_ROLE_REF"}, ["COGNITIVE_ROLE_REF"]),
    ({"cognitive_role_id"}, ["cognitive_role_id"]),
    ({"RoleContract", "role_ref"}, []),
])
def test_the_projection_scanner_flags_a_carried_projection(names, expected):
    """Substring matching, so a renamed or wrapped re-export is caught too."""
    assert _projection_hits(names) == expected


@pytest.mark.parametrize("body,expected", [
    ('{"exports": ["CognitiveRoleContract"]}', ["CognitiveRole"]),
    ('{"exports": ["cognitive_role_ref"]}', ["cognitive_role"]),
    ('{"exports": ["RoleContract"]}', []),
])
def test_the_snapshot_scanner_flags_an_exported_projection(body, expected):
    assert _snapshot_projection_hits(body) == expected


@pytest.mark.parametrize("text,expected", [
    ('dependencies = ["ugence-agentic-proposer>=0.0.1"]', [THIS_DISTRIBUTION]),
    ("from ugence_agentic_proposer import vocabulary\n", [THIS_NAMESPACE]),
    ('dependencies = ["ugence-jcs>=0.2.0"]', []),
])
def test_the_dependency_scanner_flags_a_reference_to_this_capability(text, expected):
    assert _capability_dependency_hits(text) == expected


# --------------------------------------------------------------------------- #
# The export bound (D8), checked from the shared-contract side
# --------------------------------------------------------------------------- #

def _shared_contract_names_by_regex():
    """The same discovery, done a different way, as an oracle for the scan above.

    ``_distribution_name`` parses ``pyproject.toml`` line by line; this reads the
    name with a regex instead. A narrowing to either one — a stricter filter, a
    parser that stops recognising a name form — makes the two disagree.
    """
    names = set()
    for pyproject in sorted(PACKAGES.rglob("pyproject.toml")):
        if any(part in {"build", "dist", ".venv", "node_modules"} for part in pyproject.parts):
            continue
        match = re.search(r"""^\s*name\s*=\s*['"]([^'"]+)['"]""",
                          pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        if match and "contract" in match.group(1) and match.group(1) != THIS_DISTRIBUTION:
            names.add(match.group(1))
    return names


#: The repository holds at least this many shared contract distributions. Asserting a
#: floor rather than non-emptiness is what makes a narrowed scan fail: a discovery
#: that found one package instead of all of them would still be "not empty".
MINIMUM_SHARED_CONTRACT_PACKAGES = 3


def test_shared_contract_packages_are_discovered():
    """The export bound is only enforced if the scan finds ALL the packages.

    Non-emptiness is not enough: a scan narrowed to a single distribution would
    satisfy it while leaving every other shared contract package unchecked.
    """
    found = _shared_contract_packages()
    names = {name for name, _ in found}
    assert names == _shared_contract_names_by_regex(), (
        "the discovery disagrees with an independent read of the same files: "
        f"{sorted(names ^ _shared_contract_names_by_regex())}")
    assert len(found) >= MINIMUM_SHARED_CONTRACT_PACKAGES, (
        f"only {len(found)} shared contract distributions discovered under "
        f"{PACKAGES}: {sorted(names)}")
    assert len(names) == len(found), f"duplicate discovery: {sorted(names)}"


@pytest.mark.parametrize(
    "name,root", _shared_contract_packages(), ids=lambda v: str(v)[:48])
def test_no_shared_contract_package_carries_the_role_projection(name, root):
    offenders = []
    for path in sorted((root / "src").rglob("*.py")):
        names = _defined_names(path.read_text(encoding="utf-8"), filename=str(path))
        hits = _projection_hits(names)
        if hits:
            offenders.append((path.name, hits))
    assert not offenders, f"{name} carries the projection: {offenders}"


@pytest.mark.parametrize(
    "name,root", _shared_contract_packages(), ids=lambda v: str(v)[:48])
def test_no_shared_contract_package_snapshot_carries_the_role_projection(name, root):
    """The curated public-API snapshots are the exported surface of record."""
    snapshots = sorted(root.glob("public_api.json"))
    if not snapshots:
        pytest.skip(f"{name} publishes no public_api.json snapshot")
    for snapshot in snapshots:
        hits = _snapshot_projection_hits(snapshot.read_text(encoding="utf-8"))
        assert not hits, f"{name}/{snapshot.name} exports {hits}"


@pytest.mark.parametrize(
    "name,root", _shared_contract_packages(), ids=lambda v: str(v)[:48])
def test_no_shared_contract_package_depends_on_this_capability(name, root):
    """A shared package cannot re-export what it cannot import."""
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert not _capability_dependency_hits(pyproject), f"{name} depends on this capability"
    for path in sorted((root / "src").rglob("*.py")):
        hits = _capability_dependency_hits(path.read_text(encoding="utf-8"))
        assert not hits, f"{name}/{path.name} references this capability: {hits}"


def test_the_projection_is_local_to_this_package_wherever_it_is_defined():
    """Repository-wide: the projection may exist in this package and nowhere else."""
    offenders = []
    for path in sorted(PACKAGES.rglob("*.py")):
        if PKG_ROOT in path.parents or any(
                part in {"build", "dist", ".venv", "__pycache__"} for part in path.parts):
            continue
        body = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in body for marker in PROJECTION_MARKERS):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"the projection escaped this capability: {offenders}"


# --------------------------------------------------------------------------- #
# The lifecycle-verb bound (D8), checked over this package's surface
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_no_source_name_is_a_role_lifecycle_verb(path):
    offenders = _lifecycle_offenders(
        _defined_names(path.read_text(encoding="utf-8"), filename=str(path)))
    assert not offenders, f"{path.name} exposes a lifecycle verb: {offenders}"


def _public_surface():
    """Every name reachable on the imported package: exports, class members, fields."""
    names = set()
    modules = [ap]
    for info in pkgutil.walk_packages(ap.__path__, ap.__name__ + "."):
        modules.append(importlib.import_module(info.name))
    for module in modules:
        exported = getattr(module, "__all__", None) or [
            n for n in vars(module) if not n.startswith("_")]
        names |= set(exported)
        for attr_name in exported:
            attr = getattr(module, attr_name, None)
            if isinstance(attr, type):
                # Inherited str/Enum machinery is not this package's surface.
                inherited = set(dir(str)) | set(dir(enum.Enum))
                names |= {n for n in dir(attr)
                          if not n.startswith("_") and n not in inherited}
                model_fields = getattr(attr, "model_fields", None)
                if isinstance(model_fields, dict):
                    names |= set(model_fields)
    return names


def test_the_imported_surface_exposes_no_role_lifecycle_verb():
    offenders = _lifecycle_offenders(_public_surface())
    assert not offenders, f"lifecycle verbs on the public surface: {offenders}"


def test_the_bounds_are_pinned_to_the_ratified_wording():
    """D8's two enforceable bounds, asserted by equality so neither can be relaxed."""
    assert PROJECTION_MARKERS == ("CognitiveRole", "COGNITIVE_ROLE", "cognitive_role")
    # D8 names six verbs explicitly; each must be matched by a stem in the scan.
    for verb in ("mint", "activate", "suspend", "ratify", "revoke", "replace"):
        assert _lifecycle_offenders({f"{verb}_role"}) == [f"{verb}_role"], verb
