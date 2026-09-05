"""The ADR's prohibitions, made mechanical.

A composition root is defined by what it cannot reach. These assert that over the
AST, the source text and the package metadata — not over prose.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import ugence_control_plane_root as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_control_plane_root"}

#: Everything a root must compose rather than import. governance-contracts is on
#: this list deliberately: `AuditReference` is INJECTED (D-2/D-4). A root one
#: import from the contract layer is one import from a capability.
FORBIDDEN = {
    "ugence_governance_contracts",
    # the authorities it must never become
    "risk_authority", "ugence_risk_authority_runtime", "ugence_decision_authority",
    "ugence_policy_authority", "decision_governance", "ugence_code_governance",
    "ugence_model_selection", "ugence_governance_provider_framework",
    # the packages whose records it stores references for
    "ugence_incident_response", "ugence_approval_workflow",
    "ugence_authority_directory", "ugence_ai_system_registry", "ugence_storygraph",
    # anything a console, a connector or a network client would need
    "fastapi", "flask", "django", "starlette", "uvicorn", "requests", "httpx",
    "aiohttp", "boto3", "kubernetes", "azure", "google", "openai", "pydantic",
    "sqlalchemy", "psycopg", "redis", "cryptography", "nacl", "jwt",
}


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_package_imports_only_the_standard_library():
    for source in SOURCES:
        roots = _roots(source)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (source.name, strays)
        assert not (roots & FORBIDDEN), (source.name, roots & FORBIDDEN)


def test_governance_contracts_is_injected_and_never_imported():
    """The seam the whole design rests on: the root composes, it does not depend.

    ``AuditReference`` arrives as a callable argument. If this ever became an
    import, the root would have acquired a dependency it is supposed to wire.
    """

    joined = "\n".join(source.read_text() for source in SOURCES)
    for forbidden in ("import ugence_governance_contracts",
                      "from ugence_governance_contracts"):
        assert forbidden not in joined, forbidden
    # and the seam that replaces it is actually declared
    assert "AuditReferenceFactory" in pkg.__all__


def test_no_class_takes_a_name_this_root_may_not_own():
    """Not an Authority, not the control plane, not a console (ADR D-2, D-4)."""

    prohibited = re.compile(
        r"(Authority|ControlPlane|Console|Orchestrator|Router|Gateway)$")
    for source in SOURCES:
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ClassDef):
                assert not prohibited.search(node.name), (source.name, node.name)


def test_no_module_is_named_for_something_this_root_may_not_own():
    prohibited = {"policy", "decision", "envelope", "credential", "connector",
                  "console", "authority", "router", "gateway"}
    for source in SOURCES:
        assert source.stem not in prohibited, source.name


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input. A root that read a clock could record an
    entry at an instant nobody observed."""

    clock_calls = {"now", "utcnow", "today", "time", "time_ns", "monotonic",
                   "perf_counter", "fromtimestamp"}
    for source in SOURCES:
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(
                    func, "id", "")
                assert name not in clock_calls, (source.name, name)


def test_no_second_vocabulary_is_minted():
    """The root mints no audit event type and no compensation type: Decision
    Authority's ``AuditEventType`` is frozen at 1.0.0 and owns those names."""

    exported = set(pkg.__all__)
    for forbidden in ("AuditEventType", "EventType", "AuditReference", "Validity",
                      "CompensationRequirement", "EvidenceReference"):
        assert forbidden not in exported, forbidden
    joined = "\n".join(source.read_text() for source in SOURCES)
    for node in ast.walk(ast.parse(joined)):
        if isinstance(node, ast.ClassDef):
            assert node.name not in {"AuditReference", "Validity"}, node.name


def test_nothing_here_can_decide_admit_or_execute():
    import inspect

    forbidden_names = ("decide", "authorize", "admit", "issue", "revoke", "execute",
                       "rollback", "approve", "deny", "grant", "broker", "connect",
                       "render", "serve")
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            for member, _ in inspect.getmembers(value, callable):
                assert member not in forbidden_names, (name, member)
        elif callable(value):
            assert name not in forbidden_names, name


def test_the_package_declares_no_runtime_dependency():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-control-plane-root"
    assert data["project"]["dependencies"] == [], (
        "the root composes injected collaborators; it depends on nothing")


def test_the_maturity_is_declared_and_not_overstated():
    """ADR D-1: a root over reference-grade parts is itself reference-grade."""

    assert pkg.MATURITY == "REFERENCE_GRADE"

    # The words may appear — "it is not production-ready" is the honest sentence
    # this package should contain. What must never appear is an *unnegated* one,
    # so every occurrence is required to be denied within the few words before it.
    #
    # The README and CHANGELOG are scanned too, not just src/: prose is where an
    # overclaim actually gets written, and a mutation probe caught this test
    # passing while the README claimed production-readiness.
    prose = [DIST / "README.md", DIST / "CHANGELOG.md"]
    joined = " ".join(source.read_text() for source in [*SOURCES, *prose]).lower()
    joined = re.sub(r"\s+", " ", joined)
    for overclaim in ("production-ready", "production ready", "tamper-proof",
                      "tamper proof"):
        for match in re.finditer(re.escape(overclaim), joined):
            preceding = joined[max(0, match.start() - 40):match.start()]
            assert re.search(r"\b(not|never|no|neither|nor)\b[^.]*$", preceding), (
                overclaim, preceding[-40:])
