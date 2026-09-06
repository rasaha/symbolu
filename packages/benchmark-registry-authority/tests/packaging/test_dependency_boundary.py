"""The frozen BR-1 layer plus the D-41 pair, in one direction, and none the other way.

The candidate rung's ratified release transition (D-40 as applied to
``BR-2C-RC``) admits exactly two third-party distributions — ``cryptography``
and ``PyNaCl`` — imported only inside the dedicated verifier module and only
for their D-41 roles. Every other prohibition here is unmoved.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = PKG / "src" / "ugence_benchmark_registry_authority"
PYPROJECT = (PKG / "pyproject.toml").read_text()


def _monorepo_root():
    """Walk up to the monorepo root, or return ``None`` if there is not one.

    Two properties in this module are about the **repository**, not about the
    package: that no other package imports this one, and that no other workflow
    references it. They are meaningful only when the package is sitting inside
    the monorepo. The gate-deletion mutation sweep deliberately runs the suite
    against a detached copy of the package tree, where neither question has an
    answer — so they skip there, with a stated reason, rather than failing for a
    reason that has nothing to do with the mutant under test.
    """

    for candidate in PKG.parents:
        if (candidate / ".github" / "workflows").is_dir() and (
            candidate / "packages"
        ).is_dir():
            return candidate
    return None


REPO = _monorepo_root()
_DETACHED = pytest.mark.skipif(
    REPO is None,
    reason=(
        "the package tree is detached from the monorepo (as it is under the "
        "mutation sweep); repository-scope properties have no answer here"
    ),
)

FORBIDDEN_PACKAGES = (
    "ugence_trusted_evidence_authority",
    "ugence_policy_authority",
    "risk_authority",
    "ugence_agent_value_readiness",
    "governed_value",
    "ugence_decision_authority",
    "ugence_governance_provider_framework",
    "ugence_governance_contracts",
    "ugence_action_clearance",
    "ugence_model_selection",
    "ugence_context_minimization",
    "ugence_cloud_scaling_controller",
    "ugence_agent_workforce_composer",
    "ugence_storygraph",
    "ugence_llm_steering_controller",
    "agent_runtime",
    "ugence_procurement",
)


def _absolute_imports(path):
    tree = ast.parse(path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


#: The verifier module — the only file the transition lets import the pair.
VERIFIER_MODULE = SRC / "verifier.py"

#: The ratified dependency set at the candidate rung, in declaration order:
#: the frozen BR-1 layer, then the D-41 pair, bounded on both sides in the same
#: style the trusted-evidence layer declares them (a selection, never an import).
RATIFIED_DEPENDENCIES = [
    "ugence-benchmark-registry==0.1.*",
    "cryptography>=41.0.7,<47.0.0",
    "PyNaCl>=1.5.0,<2.0.0",
]


def test_happy_the_declared_dependency_list_is_exactly_br1_plus_the_d41_pair():
    match = re.search(r"^dependencies = \[(.*?)\]", PYPROJECT, re.M | re.S)
    assert match, "no dependencies key in pyproject.toml"
    declared = re.findall(r'"([^"]+)"', match.group(1))
    assert declared == RATIFIED_DEPENDENCIES


def test_the_dependency_is_pinned_to_the_br1_zero_one_line():
    assert 'ugence-benchmark-registry==0.1.*' in PYPROJECT


def test_no_cryptographic_dependency_beyond_the_d41_pair_is_declared():
    """D-41 selected two. A third backend, a pure-Python Ed25519 or a Ugence
    authority's own implementation stays out, and the pair stays bounded."""

    match = re.search(r"^dependencies = \[(.*?)\]", PYPROJECT, re.M | re.S)
    declared = re.findall(r'"([^"]+)"', match.group(1))
    lowered = " ".join(declared).lower()
    for banned in ("ed25519", "pycryptodome", "pycrypto", "pyopenssl", "ecdsa",
                   "libsodium", "trusted-evidence", "policy-authority",
                   "risk-authority", "governance-contracts"):
        assert banned not in lowered, banned
    for pin in ("cryptography>=", "cryptography>=41.0.7,<", "PyNaCl>=1.5.0,<"):
        assert pin in " ".join(declared), pin


def test_the_d41_pair_is_imported_only_inside_the_verifier_module():
    for path in sorted(SRC.rglob("*.py")):
        imported = _absolute_imports(path) & {"cryptography", "nacl"}
        if path == VERIFIER_MODULE:
            assert imported == {"cryptography", "nacl"}, path.name
        else:
            assert imported == set(), (path.name, imported)


@pytest.mark.parametrize("forbidden", FORBIDDEN_PACKAGES)
def test_no_module_imports_a_forbidden_package(forbidden):
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if forbidden in _absolute_imports(path):
            offenders.append(path.name)
    assert offenders == [], offenders


def test_the_only_non_stdlib_imports_are_br1_and_the_pair_in_the_verifier_module():
    stdlib = {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "re",
        "types",
        "typing",
        "unicodedata",
    }
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        permitted = {"cryptography", "nacl"} if path == VERIFIER_MODULE else set()
        for module in sorted(_absolute_imports(path)):
            if module in stdlib or module == "ugence_benchmark_registry":
                continue
            if module in permitted:
                continue
            offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


NAMESPACE = "ugence_benchmark_registry_authority"


def _imports_this_package(path: pathlib.Path) -> bool:
    """Whether a Python file **imports** this package — by ``import``,
    ``from … import``, or a string literal handed to ``importlib.import_module``
    or ``__import__``.

    An import statement, not a mention. The previous form searched for the
    package name as a substring, which also matched a neighbour naming this
    package inside its *own* forbidden-import list — the opposite of an import.
    Reading the AST measures the claim the gate makes: that no other package
    depends on this one. Dynamic imports through a literal string are caught
    because they are the cheapest way to hide one; a name computed at runtime
    is outside what a static gate can see, and is not claimed.
    """

    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == NAMESPACE for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.split(".")[0] == NAMESPACE:
                return True
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in ("import_module", "__import__") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if first.value.split(".")[0] == NAMESPACE:
                        return True
    return False


def _reverse_importers(packages_root: pathlib.Path, exclude: pathlib.Path):
    offenders = []
    for path in sorted(packages_root.rglob("*.py")):
        if exclude in path.parents:
            continue
        if "__pycache__" in str(path) or "/build/" in str(path):
            continue
        try:
            if _imports_this_package(path):
                offenders.append(str(path.relative_to(packages_root.parent)))
        except (UnicodeDecodeError, OSError):  # pragma: no cover
            continue
    return offenders


@_DETACHED
def test_no_package_in_the_monorepo_imports_this_one():
    """The BR-2A **terminal state**, not a permanent invariant.

    BR-2B and later explicitly may depend on BR-2A after their own
    ratification. What this asserts is that *at BR-2A delivery* nothing does —
    so this milestone changes no other package's behaviour, and the freeze
    matrix for every neighbour is a statement about an untouched tree.

    Measured on import statements (see :func:`_imports_this_package`), so a
    neighbour that bans this package by name in its own boundary test is not
    read as depending on it.
    """

    assert _reverse_importers(REPO / "packages", PKG) == []


def test_the_reverse_import_gate_catches_a_real_import_and_ignores_a_mention(tmp_path):
    """The gate must still fail on an actual reverse import, in every spelling a
    contributor would write, and must stay silent on a name in a string."""

    packages = tmp_path / "packages"
    this = packages / "benchmark-registry-authority"
    this.mkdir(parents=True)
    (this / "own.py").write_text("import ugence_benchmark_registry_authority\n")
    neighbour = packages / "integration" / "neighbour"
    neighbour.mkdir(parents=True)
    spellings = {
        "plain.py": "import ugence_benchmark_registry_authority\n",
        "dotted.py": "import ugence_benchmark_registry_authority.api as x\n",
        "from_form.py": "from ugence_benchmark_registry_authority import api\n",
        "from_sub.py": "from ugence_benchmark_registry_authority.contracts import trust\n",
        "dynamic.py": "import importlib\nm = importlib.import_module('ugence_benchmark_registry_authority')\n",
        "dunder.py": "m = __import__('ugence_benchmark_registry_authority.api')\n",
    }
    for name, text in spellings.items():
        (neighbour / name).write_text(text)
    (neighbour / "mention.py").write_text(
        'FORBIDDEN = {"ugence_benchmark_registry_authority", "other"}\n'
        '# ugence_benchmark_registry_authority is never imported here\n'
        'doc = """ugence_benchmark_registry_authority"""\n'
    )
    (neighbour / "relative.py").write_text("from . import mention\n")
    caught = _reverse_importers(packages, this)
    assert sorted(caught) == sorted(
        f"packages/integration/neighbour/{name}" for name in spellings
    )
    assert not any(path.endswith(("mention.py", "relative.py", "own.py")) for path in caught)


@_DETACHED
def test_no_workflow_other_than_this_packages_own_references_it():
    workflows = REPO / ".github" / "workflows"
    referencing = sorted(
        path.name
        for path in workflows.glob("*.yml")
        if "benchmark-registry-authority" in path.read_text()
    )
    assert referencing == ["benchmark-registry-authority-ci.yml"]


def test_the_frozen_br1_package_directory_is_not_modified_by_this_package():
    """Nothing here writes to, imports privately from, or shadows BR-1's tree."""

    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text()
        assert "ugence_benchmark_registry.contracts" not in text, path.name
        assert "ugence_benchmark_registry._" not in text, path.name


def test_only_the_public_br1_surface_is_imported():
    """BR-1's private modules are not an API and are never reached into."""

    from ugence_benchmark_registry import api as br1_api

    imported = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == "ugence_benchmark_registry"
            ):
                imported.update(alias.name for alias in node.names)
    assert imported, "nothing is imported from BR-1 at all"
    assert imported <= set(br1_api.__all__), sorted(
        imported - set(br1_api.__all__)
    )
