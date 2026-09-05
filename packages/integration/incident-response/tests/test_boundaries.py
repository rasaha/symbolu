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

import ugence_incident_response as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_incident_response", "ugence_governance_contracts"}
FORBIDDEN = {
    # the authorities this package signals but never becomes
    "risk_authority", "ugence_risk_authority_runtime", "ugence_risk_authority_status_runtime",
    "ugence_decision_authority", "decision_governance", "ugence_policy_authority",
    "ugence_code_governance", "ugence_approval_workflow", "ugence_authority_directory",
    "ugence_ai_system_registry", "ugence_agent_runtime", "ugence_storygraph",
    # anything a store, deliverer or actuator would need
    "sqlite3", "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx",
    "aiohttp", "boto3", "kubernetes", "azure", "google", "openai", "fastapi",
    "cryptography", "nacl", "OpenSSL", "jwt",
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


def test_the_authorities_this_package_signals_are_never_imported():
    """RA-6 revokes, Decision Authority governs the remedy. This package does neither,
    and cannot reach either — the signal shape is reproduced, never imported."""

    joined = "\n".join(src.read_text() for src in SOURCES)
    for forbidden in ("from risk_authority", "import risk_authority",
                      "from ugence_risk_authority", "import ugence_risk_authority",
                      "from ugence_decision_authority", "import ugence_decision_authority",
                      "from ugence_code_governance", "import ugence_code_governance"):
        assert forbidden not in joined, forbidden


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-incident-response"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.5.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("risk-authority", "decision-authority", "code-governance",
                      "approval-workflow", "authority-directory", "pydantic", "sqlalchemy"):
        assert forbidden not in joined
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input: an incident is opened *at* an instant somebody
    observed, never at the instant the record happened to be constructed."""

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
# Naming: not an orchestrator, not an authority
# --------------------------------------------------------------------------- #
def test_nothing_here_is_named_an_orchestrator_or_an_authority():
    """The sequencing row called it an orchestrator; that word means optional workflow
    composition that acquires no authority, and this package composes no workflow."""

    for name in pkg.__all__:
        assert "Orchestrator" not in name, name
        assert not name.endswith("Authority"), name
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert "Orchestrator" not in node.name, (src.name, node.name)
                assert not node.name.endswith("Authority"), (src.name, node.name)
    code = {n for src in SOURCES for n in _identifiers(src)}
    assert not {n for n in code if "orchestrat" in n.lower()}


def test_the_package_mints_no_audit_reference_or_compensation_type():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert node.name != "AuditReference", src.name
                assert "Compensation" not in node.name, (src.name, node.name)
    from ugence_governance_contracts.contracts import audit as gc_audit

    assert pkg.AuditReference is gc_audit.AuditReference


# --------------------------------------------------------------------------- #
# It records; it never acts
# --------------------------------------------------------------------------- #
def test_no_surface_can_revoke_execute_roll_back_or_lift():
    forbidden = {"revoke", "execute", "rollback", "roll_back", "compensate", "restart",
                 "resume", "lift_containment", "clear_containment", "advance_epoch",
                 "mutate", "apply", "actuate", "scale", "patch", "deliver", "send",
                 "publish", "notify"}
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            methods = {n for n in dir(value) if not n.startswith("_")}
            assert not methods & forbidden, (name, methods & forbidden)
        assert name.lower() not in forbidden, name
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "CONTRACTS_ONLY"


def test_no_store_adapter_or_actuator_ships():
    """D-4: the platform already has six durable event stores; this adds no seventh."""

    segments = {seg for src in SOURCES for name in _identifiers(src)
                for seg in re.split(r"[^a-z0-9]+", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())}
    for word in ("sqlite", "connect", "connection", "session", "http", "url", "endpoint",
                 "client", "kubernetes", "actuator", "commit", "flush"):
        assert word not in segments, word
    module_names = {src.stem for src in SOURCES}
    for banned in ("memory", "sqlite", "store", "adapter", "connector", "client", "actuator"):
        assert banned not in module_names, banned


def test_every_record_is_frozen():
    import dataclasses

    for name in ("IncidentRecord", "ContainmentRequest", "ContainmentLift",
                 "RemediationProposal", "ReassessmentSignalPayload"):
        cls = getattr(pkg, name)
        assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen, name
