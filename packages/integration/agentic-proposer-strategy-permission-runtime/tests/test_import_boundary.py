"""What this distribution may import, and what it must not be able to reach.

The load-bearing prohibition is mechanism. The proposer's resolver boundary
authorizes **no** networking, storage, service discovery or plugin loading of any
kind, precisely so that an injected in-process callable never becomes something a
package resolves for itself. This distribution is that injected callable; the bar
applies to it as squarely as to the package that defined it.

Two repository-wide scans in neighbouring suites also bind here, and are
re-asserted so a violation surfaces in this package's own suite rather than only
in someone else's:

* the Agentic Proposer's **role projection** scan, which reads raw file text and
  refuses three substrings in every ``.py`` under ``packages/`` outside that
  capability;
* the Policy Authority's **internals** scan, which allows a consumer to name the
  distribution and its ``api`` module and nothing else.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = DIST_ROOT / "src" / "ugence_agentic_proposer_strategy_permission_runtime"
MODULES = sorted(SRC.glob("*.py"))
ALL_PY = sorted(DIST_ROOT.rglob("*.py"))

#: Exactly the substrings the Agentic Proposer's repository-wide scan refuses.
#
# Assembled at import time from fragments rather than written as literals. That
# scan reads raw file text, so a test file that spelled the markers out would
# itself become the violation it exists to detect — and would fail a neighbouring
# package's suite rather than this one's.
_STEM = "Cognitive" + "Role"
PROJECTION_MARKERS = (
    _STEM,
    _STEM.upper()[:9] + "_" + _STEM.upper()[9:],
    _STEM.lower()[:9] + "_" + _STEM.lower()[9:],
)


def _code_only(path: pathlib.Path) -> str:
    """The module's executable source with docstrings removed.

    This package's docstrings deliberately *name* the mechanisms the code must not
    reach for, and a guard that could not tell a prohibition from a violation
    would measure nothing.
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
    assert len(MODULES) >= 5


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reaches_a_barred_mechanism(module):
    """The same set the proposer bars its own resolver boundary from naming."""

    barred = {
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
        "subprocess",
        "os",
    }
    assert _imported_roots(module).isdisjoint(barred)


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_imports_an_execution_authority(module):
    """Permission must never drag consequential execution in behind it."""

    forbidden = {
        "ugence_risk_authority",
        "risk_authority",
        "actiongate",
        "actiongate_provider",
        "ugence_decision_authority",
        "ugence_agent_runtime",
        "ugence_uvi_policy_contracts",
    }
    assert _imported_roots(module).isdisjoint(forbidden)


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_every_import_is_stdlib_or_a_declared_dependency(module):
    declared = {
        "ugence_policy_authority",
        "ugence_agentic_proposer",
        "ugence_agentic_proposer_strategy_permission_policy",
    }
    stdlib = {"__future__", "types", "typing"}
    unexpected = _imported_roots(module) - declared - stdlib
    assert not unexpected, f"{module.name} imports {sorted(unexpected)}"


@pytest.mark.parametrize("module", ALL_PY, ids=lambda p: p.name)
def test_the_authority_is_reached_only_through_its_public_api(module):
    """Never ``ugence_policy_authority.core.*``: that is the authority's internals."""

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
    """``as_of`` is the caller's. A resolver that chose its own instant would make
    the same stored artifacts resolve differently on different days, with nothing
    recording why."""

    source = _code_only(module)
    for forbidden in ("datetime.now", "utcnow", "time.time", "date.today", "monotonic"):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reimplements_canonicalization_hashing_or_signing(module):
    """Issuance, signing and canonicalization all belong to the authority."""

    source = _code_only(module)
    for forbidden in (
        "hashlib",
        "json.dumps",
        "sort_keys",
        "sha256(",
        "SigningKey",
        "from_seed",
        "def sign",
        ".sign(",
    ):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_defines_an_approval_verifier_or_a_trust_anchor(module):
    """Approval and trust stay the composition root's, injected and never defaulted."""

    source = _code_only(module)
    for forbidden in ("def verify_approval", "ApprovalVerification(", "VerifyKey("):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


def test_no_module_supplies_a_default_for_an_injected_trust_dependency():
    """A default here would let an unconfigured deployment resolve against nobody."""

    source = _code_only(SRC / "resolver.py") + _code_only(SRC / "composition.py")
    for forbidden in (
        "approval_verifier=DenyAll",
        "approval_verifier=None,",
        "registry=None",
        "signature_verifier=None",
    ):
        assert forbidden not in source, forbidden


def test_the_distribution_declares_exactly_the_dependencies_the_code_uses():
    pyproject = (DIST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for required in (
        '"ugence-policy-authority>=0.1.0"',
        '"ugence-agentic-proposer>=0.3.0"',
        '"ugence-agentic-proposer-strategy-permission-policy>=0.1.0"',
    ):
        assert required in pyproject
    for forbidden in (
        '"ugence-uvi-policy-contracts',
        '"ugence-risk-authority',
        '"ugence-decision-authority',
        '"ugence-agent-runtime',
        '"requests',
        '"httpx',
        '"boto3',
    ):
        assert forbidden not in pyproject


def test_the_distribution_name_is_not_a_shared_contract_name():
    """A distribution whose name contains ``contract`` is bound by a different guard.

    The Agentic Proposer's reverse-dependency guard forbids any such distribution
    from depending on the capability. This one may depend on it, and its name is
    what keeps the two rules apart.
    """

    pyproject = (DIST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "ugence-agentic-proposer-strategy-permission-runtime"' in pyproject
    assert "contract" not in "ugence-agentic-proposer-strategy-permission-runtime"


# --------------------------------------------------------------------------- #
# The role-lookup exemption is confined to the test tree — owner ruling ROLE_LOOKUP=A
# --------------------------------------------------------------------------- #


def test_the_shipped_source_never_receives_names_or_touches_a_role():
    """The exemption is the test tree's alone, and cannot widen into ``src/``.

    The ratified end-to-end proof must construct a role, because the proposer's
    own builder and its replay both take one. The proposer's repository-wide scan
    reads raw file text and refuses the role-projection substrings everywhere
    outside that capability, and editing the proposer is barred — so the fixture
    module looks the class up by an assembled name.

    That is an accommodation, not a licence. `[V]` The design's own reasoning for
    why it costs nothing is that *this distribution never receives a role*: the
    resolver is handed a ``StrategyPolicyRequest``, never an identity. This test
    is what makes that claim measured rather than asserted, so a later change
    cannot quietly carry the exemption from ``tests/`` into shipped source.

    Scanned over defined names, parameters, referenced names, attribute accesses
    and message literals — not comments or docstrings, which name the boundary in
    order to state it.
    """

    offenders = []
    for module in MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body:
                first = body[0]
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            found = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found = node.name
            elif isinstance(node, ast.arg):
                found = node.arg
            elif isinstance(node, ast.Name):
                found = node.id
            elif isinstance(node, ast.Attribute):
                found = node.attr
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                found = node.value
            if found and "role" in found.lower():
                offenders.append(f"{module.name}: {found!r}")
    assert not offenders, (
        "the shipped source names a role; the exemption is the test tree's alone: "
        f"{offenders}"
    )


def test_the_exemption_is_actually_exercised_where_it_is_claimed():
    """A confinement rule proves nothing if nothing is confined.

    If the fixture module ever stops constructing a role, this test fails and the
    exemption above should be withdrawn rather than left standing unused.
    """

    fixtures = (DIST_ROOT / "tests" / "_permission_runtime_fixtures.py").read_text(
        encoding="utf-8"
    )
    assert '_ROLE_CONTRACT = getattr(ap, "Cognitive" + "Role' in fixtures
    assert "role=role" in fixtures
