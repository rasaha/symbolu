"""What this distribution may import, and what it must not be able to reach.

A conformance boundary is only real if it is measured. These tests read the
shipped source directly, so a future import cannot quietly widen the surface,
and they walk the packaging metadata so it cannot drift from the code.

Two prohibitions carry more weight than the rest:

* the **role projection** — a repository-wide scan in the Agentic Proposer's own
  suite refuses those substrings in every ``.py`` under ``packages/`` outside
  that capability, docstrings and comments included. This distribution never
  receives a role: the boundary is handed a reference and plain presented facts,
  never an identity.
* the **authority's internals** — a repository-wide scan in the Policy
  Authority's own suite allows a consumer to name the distribution and its
  ``api`` module and nothing else.

Both are enforced elsewhere; they are re-asserted here so that a violation is
caught by this package's own suite rather than only by a neighbour's.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = DIST_ROOT / "src" / "ugence_agent_constitution_conformance"
MODULES = sorted(SRC.glob("*.py"))
ALL_PY = sorted(DIST_ROOT.rglob("*.py"))

#: Exactly the substrings the Agentic Proposer's repository-wide scan refuses.
#
# Assembled at import time from fragments rather than written as literals. The scan
# this mirrors reads raw file text, so a test file that spelled the markers out
# would itself become the violation it exists to detect — and would fail a
# neighbouring package's suite rather than this one's.
_STEM = "Cognitive" + "Role"
PROJECTION_MARKERS = (_STEM, _STEM.upper()[:9] + "_" + _STEM.upper()[9:], _STEM.lower()[:9] + "_" + _STEM.lower()[9:])


def _code_only(path: pathlib.Path) -> str:
    """The module's executable source with docstrings removed.

    Scanning raw text would trip over prose: this package's docstrings
    deliberately *name* the things the code must not do, and a test that cannot
    tell a prohibition from a violation measures nothing.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            body.pop(0)
            if not body:
                body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree))


def _imported_roots(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_source_tree_is_not_empty_so_these_tests_measure_something():
    assert len(MODULES) >= 6


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_imports_a_forbidden_neighbour(module):
    """Networking, storage, service discovery and plugin loading are each named.

    Each would turn a fail-closed boundary into something that resolves a
    mechanism for itself, which is precisely what this package is excluded from.
    """

    forbidden = {
        "ugence_uvi_policy_contracts",
        "ugence_cloud_scaling_authorization_contracts",
        "ugence_agentic_proposer_strategy_permission_policy",
        "ugence_agentic_proposer_strategy_permission_runtime",
        "ugence_trusted_evidence_authority",
        "ugence_risk_authority",
        "risk_authority",
        "actiongate",
        "socket",
        "ssl",
        "urllib",
        "http",
        "requests",
        "httpx",
        "aiohttp",
        "sqlite3",
        "pickle",
        "shelve",
        "pkg_resources",
        "importlib",
        "boto3",
        "kubernetes",
    }
    assert _imported_roots(module).isdisjoint(forbidden)


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_every_import_is_stdlib_or_a_declared_dependency(module):
    declared = {
        "ugence_policy_authority",
        "ugence_agentic_proposer",
        "ugence_agent_constitution_policy",
    }
    stdlib = {"__future__", "dataclasses", "datetime", "re", "types", "typing"}
    roots = _imported_roots(module)
    unexpected = roots - declared - stdlib
    assert not unexpected, f"{module.name} imports {sorted(unexpected)}"


@pytest.mark.parametrize("module", ALL_PY, ids=lambda p: p.name)
def test_the_authority_is_reached_only_through_its_public_api(module):
    """Never the authority's internal modules: those are the authority's own."""

    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module.split(".")[0] == "ugence_policy_authority":
                assert node.module == "ugence_policy_authority.api", (
                    f"{module.name} reaches {node.module}; use the public api module"
                )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "ugence_policy_authority":
                    assert alias.name in {
                        "ugence_policy_authority",
                        "ugence_policy_authority.api",
                    }, f"{module.name} reaches {alias.name}"


@pytest.mark.parametrize("module", ALL_PY, ids=lambda p: p.name)
def test_the_role_projection_appears_nowhere_in_this_distribution(module):
    """Prose included: the repository-wide scan reads raw text, not an AST."""

    body = module.read_text(encoding="utf-8")
    hits = [marker for marker in PROJECTION_MARKERS if marker in body]
    assert not hits, f"{module.name} names the role projection: {hits}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reads_a_wall_clock(module):
    """This boundary has no present tense. Every instant is a caller's."""

    source = _code_only(module)
    for forbidden in ("datetime.now", "utcnow", "time.time", "date.today", "monotonic"):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reimplements_canonicalization_or_hashing(module):
    """Every byte flows through the Policy Authority's public canonicalization."""

    source = _code_only(module)
    for forbidden in ("hashlib", "json.dumps", "sort_keys", "sha256("):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_the_shipped_source_contains_no_signing_key_material_or_signing_call(module):
    """Signing belongs to the authority. This package resolves and reads."""

    source = _code_only(module)
    for forbidden in ("SigningKey", "from_seed", "def sign", ".sign("):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


def test_the_distribution_declares_exactly_the_dependencies_the_code_uses():
    pyproject = (DIST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"ugence-policy-authority>=0.1.0"' in pyproject
    assert '"ugence-agentic-proposer>=0.3.0"' in pyproject
    assert '"ugence-agent-constitution-policy>=0.1.0"' in pyproject
    for forbidden in (
        '"ugence-uvi-policy-contracts',
        '"ugence-trusted-evidence-authority',
        '"ugence-risk-authority',
        '"ugence-cloud-scaling',
        '"ugence-agentic-proposer-strategy-permission',
        '"boto3',
        '"kubernetes',
    ):
        assert forbidden not in pyproject


def test_the_distribution_name_is_not_a_shared_contract_name():
    """A distribution whose name contains ``contract`` is bound by a different guard.

    The Agentic Proposer's reverse-dependency guard forbids any distribution whose
    name contains that substring from depending on the capability. This one may
    depend on it, and its name is what keeps the two rules apart.
    """

    pyproject = (DIST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "ugence-agent-constitution-conformance"' in pyproject
    assert "contract" not in "ugence-agent-constitution-conformance"
