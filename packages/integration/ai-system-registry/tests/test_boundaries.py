"""Import boundary, the clock-free rule, the declared dependency set, the naming
prohibitions, and the absence of anything that could admit, gate or attest —
asserted over source, AST and metadata.

These are the ADR's prohibitions made mechanical.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import ugence_ai_system_registry as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_ai_system_registry", "ugence_governance_contracts"}
FORBIDDEN = {
    # neighbours whose nouns or ledgers this package must not duplicate
    "ugence_agent_runtime", "ugence_approval_workflow", "ugence_authority_directory",
    "ugence_decision_authority", "decision_governance", "ugence_policy_authority",
    "risk_authority", "ugence_risk_authority_runtime", "ugence_model_selection",
    "ugence_benchmark_registry", "ugence_benchmark_registry_authority", "ugence_storygraph",
    # anything a store, connector or attestation service would need
    "sqlite3", "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx",
    "aiohttp", "boto3", "kubernetes", "azure", "google", "openai", "fastapi",
    "cryptography", "nacl", "OpenSSL", "ldap3", "jwt",
}


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _identifiers(path: pathlib.Path) -> set[str]:
    """Every name and string literal the *code* uses, with docstrings excluded.

    Prose is allowed to name what the package refuses to do — the code is not.
    """

    tree = ast.parse(path.read_text(), filename=str(path))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            names.add(node.value)
    return names


def test_source_imports_only_stdlib_and_governance_contracts():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN), (src.name, roots & FORBIDDEN)


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-ai-system-registry"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.4.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("agent-runtime", "approval-workflow", "authority-directory",
                      "decision-authority", "risk-authority", "policy-authority",
                      "model-selection", "benchmark-registry", "pydantic", "sqlalchemy"):
        assert forbidden not in joined
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input, so a registration lapses without a sweeper."""

    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                    "perf_counter", "uuid4", "uuid1", "urandom",
                                    "random"), (src.name, name)
                if name == "astimezone":
                    assert node.args, f"{src.name}: zero-argument astimezone infers the local zone"


# --------------------------------------------------------------------------- #
# Naming: not an Authority, not a Portfolio
# --------------------------------------------------------------------------- #
def test_no_exported_type_is_an_authority_or_a_portfolio():
    for name in pkg.__all__:
        assert not name.endswith("Authority"), name
        assert "Portfolio" not in name, name
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert not node.name.endswith("Authority"), (src.name, node.name)
                assert "Portfolio" not in node.name, (src.name, node.name)


def test_nothing_here_is_a_second_portfolio_ledger():
    """WorkflowPortfolio in packages/runtime/agent-runtime stays the only one."""

    code = "\n".join(sorted(n for src in SOURCES for n in _identifiers(src))).lower()
    for word in ("portfolio", "priority", "fairness", "quantum", "budget", "schedul"):
        assert word not in code, word


def test_the_package_defines_no_system_identity_of_its_own():
    """It re-exports AssessedSystemBinding; it never redefines it."""

    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert node.name != "AssessedSystemBinding", src.name
                assert "SystemBinding" not in node.name, (src.name, node.name)
    from ugence_governance_contracts.contracts import system_identity as gc

    assert pkg.AssessedSystemBinding is gc.AssessedSystemBinding
    assert pkg.SystemBindingAuthenticityStatus is gc.SystemBindingAuthenticityStatus


# --------------------------------------------------------------------------- #
# Contracts only: nothing that could admit, gate, persist or attest
# --------------------------------------------------------------------------- #
def test_no_surface_can_admit_gate_promote_or_attest():
    forbidden = {"admit", "register", "gate", "promote", "approve", "resolve", "attest",
                 "sign", "verify", "authorize", "authenticate", "revoke", "sync", "push",
                 "save", "store", "commit", "upsert", "delete"}
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            methods = {n for n in dir(value) if not n.startswith("_")}
            assert not methods & forbidden, (name, methods & forbidden)
        assert name.lower() not in forbidden, name
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "CONTRACTS_ONLY"


def test_no_store_adapter_or_connector_ships():
    """D-5 is held structurally: there is nothing here that could reach a system of record."""

    # Match whole word segments, so "supersession" is not read as "session".
    segments = {seg for src in SOURCES for name in _identifiers(src)
                for seg in re.split(r"[^a-z0-9]+", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())}
    for word in ("sqlite", "connect", "connection", "session", "http", "https", "url",
                 "endpoint", "client", "servicenow", "jira", "cmdb", "scim", "ldap"):
        assert word not in segments, word
    module_names = {src.stem for src in SOURCES}
    for banned in ("memory", "sqlite", "store", "adapter", "connector", "client"):
        assert banned not in module_names, banned


def test_the_registration_cannot_be_mutated_after_construction():
    import dataclasses

    import pytest

    from _fixtures import registration

    reg = registration()
    assert dataclasses.is_dataclass(reg) and reg.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        reg.classification_label = "low-risk"  # type: ignore[misc]
