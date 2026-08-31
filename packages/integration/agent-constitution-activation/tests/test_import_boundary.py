"""What this distribution may import, and what it must never be able to reach.

Three disciplines are measured over the shipped source, so a future edit cannot
quietly widen the surface:

* **the custody bound** (`ACC-IA-2`) — the source cannot mint, read or persist
  key material: no key or signer construction, no randomness, no environment or
  filesystem access, no clock reads, no hashing of its own. Signer and
  verifiers arrive already constructed, and the AST proves the package could
  not build one if asked.
* **the authority's internals** — the Policy Authority is reached through its
  public ``api`` module only, on the repository-wide rule the authority's own
  suite enforces; the conformance package is reached through its top level and
  its ``composition`` module (the seam the ruled scope names), nothing else.
* **the role projection** — a repository-wide scan in the Agentic Proposer's
  own suite refuses those substrings in every ``.py`` under ``packages/``
  outside that capability, prose included. This distribution never receives a
  role: it is re-asserted here so a violation is caught by this package's own
  suite rather than only by a neighbour's.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = DIST_ROOT / "src" / "ugence_agent_constitution_activation"
MODULES = sorted(SRC.glob("*.py"))
#: Every committed text file under the distribution — the `ACC-PR-IA-1`
#: extension: the projection scan must reach the committed pilot declaration
#: (and any future non-``.py`` file), not only Python source.
ALL_TEXT = sorted(
    p
    for p in DIST_ROOT.rglob("*")
    if p.is_file()
    and p.suffix in {".py", ".json", ".md", ".toml", ".txt", ".cfg", ".typed"}
    and not any(part in {"build", "dist", ".venv", "__pycache__"} for part in p.parts)
)

#: The only top-level modules the shipped source may import.
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "dataclasses",
    "datetime",
    "types",
    "typing",
    "ugence_policy_authority",
    "ugence_agent_constitution_policy",
    "ugence_agent_constitution_conformance",
}

#: Names whose mere reference in the source would be custody, clock, randomness,
#: environment or filesystem capability. Matched as EXACT identifier/attribute
#: names, not substrings — ``signer`` and ``signature_alg`` are lawful words.
CUSTODY_BARRED_NAMES = {
    "SigningKey",
    "VerifyKey",
    "Ed25519PolicySigner",
    "PolicyKeyRing",
    "from_seed",
    "generate",
    "urandom",
    "token_bytes",
    "environ",
    "getenv",
    "open",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "now",
    "utcnow",
    "today",
    "sha256",
    "sign",
}

#: Exactly the substrings the Agentic Proposer's repository-wide scan refuses.
#
# Assembled at import time from fragments rather than written as literals: the
# scan this mirrors reads raw file text, so a test file that spelled the markers
# out would itself become the violation it exists to detect.
_STEM = "Cognitive" + "Role"
PROJECTION_MARKERS = (
    _STEM,
    _STEM.upper()[:9] + "_" + _STEM.upper()[9:],
    _STEM.lower()[:9] + "_" + _STEM.lower()[9:],
)


def _imported_modules(path: pathlib.Path):
    """Every absolute module path this file imports, with its import roots."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


def _referenced_names(path: pathlib.Path):
    """Every identifier, attribute and imported binding the module references."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.name for alias in node.names)
    return names


def test_the_source_tree_is_not_empty_so_these_tests_measure_something():
    assert len(MODULES) >= 6


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_only_the_allowed_roots_are_imported(module):
    roots = {m.split(".")[0] for m in _imported_modules(module)}
    assert roots <= ALLOWED_IMPORT_ROOTS, roots - ALLOWED_IMPORT_ROOTS


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_the_authority_is_reached_through_api_only(module):
    for name in _imported_modules(module):
        if name == "ugence_policy_authority" or name.startswith(
            "ugence_policy_authority."
        ):
            assert name == "ugence_policy_authority.api", name


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_the_conformance_package_is_reached_at_its_sanctioned_seams(module):
    allowed = {
        "ugence_agent_constitution_conformance",
        "ugence_agent_constitution_conformance.composition",
    }
    for name in _imported_modules(module):
        if name.startswith("ugence_agent_constitution_conformance"):
            assert name in allowed, name


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_custody_clock_randomness_or_filesystem_name_is_referenced(module):
    hits = _referenced_names(module) & CUSTODY_BARRED_NAMES
    assert not hits, f"{module.name} references {sorted(hits)}"


def test_the_custody_scan_would_catch_a_violation():
    """A scanner is only evidence if a planted violation trips it."""

    planted = "from ugence_policy_authority.api import SigningKey\n"
    tree = ast.parse(planted)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.name for alias in node.names)
    assert names & CUSTODY_BARRED_NAMES


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_the_source_never_imports_the_proposer(module):
    """The bind leg lives in this suite, driving the proposer's own builders;
    the shipped source has no proposer dependency at all."""

    for name in _imported_modules(module):
        assert not name.startswith("ugence_agentic_proposer"), name


@pytest.mark.parametrize("path", ALL_TEXT, ids=lambda p: p.name)
def test_the_role_projection_never_appears_in_this_distribution(path):
    body = path.read_text(encoding="utf-8", errors="ignore")
    hits = [marker for marker in PROJECTION_MARKERS if marker in body]
    assert not hits, f"{path.name} carries {hits}"


def test_no_key_material_shaped_literal_exists_in_the_source():
    """No bytes literal long enough to be a seed, and no long hex-string
    literal, exists in the shipped source. Digest examples and key bytes alike
    have no business there — every digest the package handles arrives at run
    time from the authority."""

    for module in MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (bytes, bytearray)):
                    assert len(node.value) < 16, f"{module.name}: bytes literal"
                if isinstance(node.value, str) and len(node.value) >= 40:
                    stripped = node.value.replace(" ", "")
                    assert not all(
                        c in "0123456789abcdefABCDEF" for c in stripped
                    ), f"{module.name}: hex-shaped literal"
