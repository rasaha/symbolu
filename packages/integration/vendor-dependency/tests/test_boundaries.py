"""Import boundary, the clock-free rule, the declared dependency set, the naming
prohibitions, and the structural inability to resolve or verify a policy
reference, score or grade risk, contact a vendor, or persist — asserted over
source, AST and metadata.

These are the rulings VR-1 to VR-5 made mechanical.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import ugence_vendor_dependency as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_vendor_dependency", "ugence_governance_contracts"}
FORBIDDEN = {
    # the three the rulings name: Policy Authority (VR-4), Risk Authority, the registry (VR-2)
    "ugence_policy_authority", "risk_authority", "ugence_risk_authority_runtime",
    "ugence_risk_authority_evidence_runtime", "ugence_ai_system_registry",
    # neighbours whose nouns this package must not duplicate
    "ugence_procurement", "ugence_data_use_admission", "ugence_agent_runtime",
    "ugence_approval_workflow", "ugence_authority_directory", "ugence_decision_authority",
    "decision_governance", "ugence_model_selection", "ugence_benchmark_registry",
    "ugence_storygraph", "ugence_incident_response", "ugence_actiongate_provider",
    # anything a store, connector, gateway, scorer or verifier would need
    "sqlite3", "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx",
    "aiohttp", "boto3", "kubernetes", "azure", "google", "openai", "anthropic",
    "fastapi", "cryptography", "nacl", "OpenSSL", "ldap3", "jwt", "socket", "ssl",
    "urllib", "http", "asyncio", "subprocess", "smtplib", "email", "re",
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


def _segments() -> set[str]:
    """Whole word segments of every code identifier, so "supersession" is not read
    as "session" and "resolved" in prose is not read as "resolve" in code."""

    return {seg for src in SOURCES for name in _identifiers(src)
            for seg in re.split(r"[^a-z0-9]+", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())}


# --------------------------------------------------------------------------- #
# Import boundary and declared dependencies
# --------------------------------------------------------------------------- #
def test_source_imports_only_stdlib_and_governance_contracts():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN), (src.name, roots & FORBIDDEN)


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-vendor-dependency"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.7.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("policy-authority", "risk-authority", "risk_authority",
                      "ai-system-registry", "data-use-admission", "procurement",
                      "agent-runtime", "approval-workflow", "authority-directory",
                      "decision-authority", "model-selection", "benchmark-registry",
                      "pydantic", "sqlalchemy", "requests", "httpx"):
        assert forbidden not in joined, forbidden
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input, so a declaration lapses without a sweeper."""

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
# Naming (VR-1); mints no identity and no vocabulary (VR-2, VR-3, VR-5)
# --------------------------------------------------------------------------- #
def test_no_exported_type_is_an_authority_gateway_supplier_or_registry():
    for name in pkg.__all__:
        for noun in ("Authority", "Gateway", "Supplier", "Registry", "Registration"):
            assert noun not in name, (name, noun)
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                for noun in ("Authority", "Gateway", "Supplier", "Registry", "Registration"):
                    assert noun not in node.name, (src.name, node.name, noun)


def test_the_package_defines_no_system_identity_and_no_label_of_its_own():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert "SystemBinding" not in node.name, (src.name, node.name)
                assert not node.name.endswith("Label"), (src.name, node.name)
                assert "Risk" not in node.name, (src.name, node.name)
    from ugence_governance_contracts.contracts import system_identity as gc_identity
    from ugence_governance_contracts.contracts import vendor_risk as gc_label

    assert pkg.AssessedSystemBinding is gc_identity.AssessedSystemBinding
    assert pkg.SystemBindingAuthenticityStatus is gc_identity.SystemBindingAuthenticityStatus
    assert pkg.VendorRiskLabel is gc_label.VendorRiskLabel


# --------------------------------------------------------------------------- #
# Contracts only: structurally unable to resolve, verify, score, grade,
# contact, persist or decide
# --------------------------------------------------------------------------- #
def test_no_surface_can_resolve_verify_score_grade_or_decide():
    forbidden = {"resolve", "verify", "fetch", "lookup", "score", "grade", "rate", "rank",
                 "assess", "evaluate", "decide", "approve", "reject", "authorize", "admit",
                 "gate", "promote", "attest", "sign", "revoke", "sync", "push", "save",
                 "store", "commit", "upsert", "delete", "contact", "notify", "send", "call",
                 "connect", "register"}
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            methods = {n for n in dir(value) if not n.startswith("_")}
            assert not methods & forbidden, (name, methods & forbidden)
        assert name.lower() not in forbidden, name
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "CONTRACTS_ONLY"


def test_the_code_names_none_of_the_things_it_refuses_to_do():
    """VR-2, VR-3, VR-4 and the contracts-only posture, held over code identifiers.

    Docstrings may say "resolve" or "score" to state what the package refuses; the
    code may not, because a function that could do it would have to name it.
    """

    segments = _segments()
    for word in (
        # persistence, transport, connectors, gateways
        "sqlite", "connect", "connection", "session", "http", "https", "url", "endpoint",
        "client", "socket", "gateway", "proxy", "smtp", "email", "webhook",
        # policy resolution and verification (VR-4)
        "resolve", "resolver", "verify", "verifier", "fetch", "lookup", "signature",
        # scoring, grading, eligibility (VR-3)
        "score", "grade", "rating", "severity", "tier", "rank", "weight", "eligible",
        "eligibility", "approve", "approved", "reject", "sanction", "dominates",
        # the registry (VR-2)
        "registry", "registration", "registered",
        # a procurement counterparty's vocabulary, which this package does not share
        "supplier", "purchase", "invoice", "procurement",
    ):
        assert word not in segments, word
    module_names = {src.stem for src in SOURCES}
    for banned in ("memory", "sqlite", "store", "adapter", "connector", "client", "gateway",
                   "scorer", "engine", "questionnaire", "resolver", "verifier"):
        assert banned not in module_names, banned


def test_no_field_could_carry_an_address_or_a_credential():
    """The declaration references a vendor; it can never reach one. Pinned by field set."""

    import dataclasses

    names = [f.name for f in dataclasses.fields(pkg.VendorDependencyDeclaration)]
    assert names == ["declaration_id", "tenant_id", "binding", "vendor_ref", "risk_posture",
                     "policy_ref", "validity", "supersedes", "declared_by", "correlation_id",
                     "notes"]
    for forbidden in ("url", "endpoint", "address", "api_key", "token", "credential", "secret",
                      "contact", "email", "score", "grade", "registration_id", "registration"):
        assert forbidden not in names, forbidden


def test_the_declaration_cannot_be_mutated_after_construction():
    import dataclasses

    import pytest

    from _fixtures import declaration

    d = declaration()
    assert dataclasses.is_dataclass(d) and d.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.policy_ref = "policy://other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.risk_posture = pkg.VendorRiskLabel("low")  # type: ignore[misc]
