"""Import boundary, the clock-free rule, the declared dependency set, the naming
prohibitions, and the structural inability to inspect, classify, redact, minimize,
persist, admit, authorize, select, enforce or govern egress — asserted over
source, AST and metadata.

These are the rulings DE-1 to DE-5 made mechanical.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import ugence_data_use_admission as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_data_use_admission", "ugence_governance_contracts"}
FORBIDDEN = {
    # the two residency evaluators DE-2 keeps split, and the seam DE-1 sits above
    "ugence_actiongate_provider", "actiongate_provider", "ugence_model_selection",
    "ugence_context_minimization",
    # neighbours whose nouns or ledgers this package must not duplicate
    "ugence_agent_runtime", "ugence_approval_workflow", "ugence_authority_directory",
    "ugence_ai_system_registry", "ugence_decision_authority", "decision_governance",
    "ugence_policy_authority", "risk_authority", "ugence_risk_authority_runtime",
    "ugence_benchmark_registry", "ugence_storygraph", "ugence_incident_response",
    # anything a store, connector, proxy, redactor or classifier would need
    "sqlite3", "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx",
    "aiohttp", "boto3", "kubernetes", "azure", "google", "openai", "anthropic",
    "fastapi", "cryptography", "nacl", "OpenSSL", "ldap3", "jwt", "socket", "ssl",
    "urllib", "http", "asyncio", "subprocess", "presidio", "spacy", "re",
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
    as "session" and "admission" (the package's own name) is not read as "admit"."""

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
    assert data["project"]["name"] == "ugence-data-use-admission"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.6.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("context-minimization", "actiongate", "model-selection",
                      "agent-runtime", "approval-workflow", "authority-directory",
                      "ai-system-registry", "decision-authority", "risk-authority",
                      "policy-authority", "benchmark-registry", "pydantic", "sqlalchemy",
                      "requests", "httpx"):
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
# Naming: not an Authority (DE-4); mints no identity and no vocabulary (DE-5)
# --------------------------------------------------------------------------- #
def test_no_exported_type_is_an_authority():
    for name in pkg.__all__:
        assert not name.endswith("Authority"), name
        assert "Authority" not in name, name
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert "Authority" not in node.name, (src.name, node.name)


def test_the_package_defines_no_system_identity_and_no_label_of_its_own():
    """It re-exports AssessedSystemBinding and DataClassificationLabel; it never
    redefines either."""

    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert "SystemBinding" not in node.name, (src.name, node.name)
                assert not node.name.endswith("Label"), (src.name, node.name)
                assert "Classification" not in node.name, (src.name, node.name)
    from ugence_governance_contracts.contracts import data_classification as gc_label
    from ugence_governance_contracts.contracts import system_identity as gc_identity

    assert pkg.AssessedSystemBinding is gc_identity.AssessedSystemBinding
    assert pkg.SystemBindingAuthenticityStatus is gc_identity.SystemBindingAuthenticityStatus
    assert pkg.DataClassificationLabel is gc_label.DataClassificationLabel


# --------------------------------------------------------------------------- #
# Contracts only: structurally unable to inspect, classify, redact, minimize,
# persist, admit, authorize, select, enforce or govern egress
# --------------------------------------------------------------------------- #
def test_no_surface_can_admit_authorize_classify_or_enforce():
    forbidden = {"admit", "classify", "gate", "promote", "approve", "resolve", "attest",
                 "sign", "verify", "authorize", "authenticate", "revoke", "sync", "push",
                 "save", "store", "commit", "upsert", "delete", "redact", "minimize",
                 "enforce", "evaluate", "decide", "select_model", "inspect", "scan"}
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            methods = {n for n in dir(value) if not n.startswith("_")}
            assert not methods & forbidden, (name, methods & forbidden)
        assert name.lower() not in forbidden, name
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "CONTRACTS_ONLY"


def test_the_code_names_none_of_the_things_it_refuses_to_do():
    """DE-1, DE-2 and the contracts-only posture, held over code identifiers.

    Docstrings may say "admit" or "egress" to state what the package refuses; the
    code may not, because a function that could do it would have to name it.
    """

    segments = _segments()
    for word in (
        # persistence, transport, connectors
        "sqlite", "connect", "connection", "session", "http", "https", "url", "endpoint",
        "client", "socket", "proxy",
        # payload inspection, redaction, minimization, classification
        "payload", "content", "body", "redact", "redaction", "minimize", "minimization",
        "classify", "classifier", "scan", "inspect", "pii", "regex",
        # admission, authorization, enforcement, model selection
        "admit", "admits", "authorize", "authorization", "enforce", "gate", "allow",
        "deny", "permit", "model", "candidate", "eligib",
        # residency evaluation (DE-2) — recorded as a label, never evaluated
        "region", "jurisdiction", "residency_required", "allowed_region",
        "data_residency_allowed",
        # result egress (DE-1)
        "egress", "output", "response", "completion", "result",
    ):
        assert word not in segments, word
    module_names = {src.stem for src in SOURCES}
    for banned in ("memory", "sqlite", "store", "adapter", "connector", "client", "proxy",
                   "redact", "redactor", "minimizer", "classifier", "engine", "egress"):
        assert banned not in module_names, banned


def test_no_field_could_carry_a_payload():
    """The declaration references data; it never holds it. Pinned by field set."""

    import dataclasses

    names = [f.name for f in dataclasses.fields(pkg.DataUseDeclaration)]
    assert names == ["declaration_id", "tenant_id", "binding", "data_ref", "classification",
                     "purpose_label", "validity", "residency_label", "supersedes",
                     "declared_by", "correlation_id", "notes"]
    for forbidden in ("data", "payload", "content", "body", "record", "value", "text",
                      "sample", "rows", "bytes", "blob"):
        assert forbidden not in names, forbidden


def test_the_declaration_cannot_be_mutated_after_construction():
    import dataclasses

    import pytest

    from _fixtures import declaration

    d = declaration()
    assert dataclasses.is_dataclass(d) and d.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.purpose_label = "something-else"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.residency_label = "eu"  # type: ignore[misc]
