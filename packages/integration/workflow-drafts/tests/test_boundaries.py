"""The ruling's prohibitions made mechanical: stdlib only, no clock, no dependency,
nothing that could approve, compile, publish, export, authenticate or execute, and no
lifecycle but DRAFT — asserted over source, AST and metadata."""

from __future__ import annotations

import ast
import pathlib
import re
import sys

try:  # Python 3.11+ ships tomllib; 3.10 resolves the same parser from tomli.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only a <3.10 run takes this branch
    import tomli as tomllib  # type: ignore[no-redef]

import ugence_workflow_drafts as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
FORBIDDEN_IMPORTS = {
    # the packages a draft must never reach on its own: the compiler, approval, the
    # runtime, the authorities, the registry it links to by reference only
    "ugence_policy_workflow_compiler", "ugence_approval_workflow", "ugence_authority_directory",
    "ugence_agent_runtime", "ugence_decision_authority", "ugence_policy_authority",
    "ugence_ai_system_registry", "ugence_agent_workforce_composer", "ugence_governance_contracts",
    "ugence_clearance_export", "ugence_action_clearance",
    # anything a network, a server, a credential or a second store would need
    "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx", "aiohttp", "boto3",
    "kubernetes", "azure", "google", "openai", "fastapi", "cryptography", "nacl", "jwt",
    "socket", "http", "urllib", "ssl", "subprocess",
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
    """Every name and string literal the *code* uses, docstrings excluded: prose may
    name what the package refuses to do, the code may not."""

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
        elif isinstance(node, (ast.arg,)):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            names.add(node.value)
    return names


def _segments(names: set[str]) -> set[str]:
    return {seg for name in names
            for seg in re.split(r"[^a-z0-9]+", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())}


def test_source_imports_only_the_stdlib():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - {"ugence_workflow_drafts", "__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN_IMPORTS), (src.name, roots & FORBIDDEN_IMPORTS)


def test_pyproject_declares_no_dependency_and_the_exact_version():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-workflow-drafts"
    assert data["project"]["dependencies"] == []
    assert data["project"]["license"] == {"text": "Proprietary"}
    assert (DIST / "LICENSE").read_text().strip().startswith("Proprietary")
    assert pkg.__version__ == "0.1.0"


def test_no_clock_and_no_randomness_is_read_anywhere():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic", "perf_counter",
                                    "uuid4", "uuid1", "urandom", "random", "astimezone"), (src.name, name)


def test_exactly_one_store_module_is_ruled_and_it_names_no_network():
    assert {src.stem for src in SOURCES} & {"durable"} == {"durable"}
    assert not any(src.stem in ("memory", "sqlite", "store", "adapter", "connector", "client")
                   for src in SOURCES)
    contract_sources = [src for src in SOURCES if src.stem != "durable"]
    segments = _segments({n for src in contract_sources if src.stem != "__init__"
                          for n in _identifiers(src)})
    for word in ("sqlite", "connect", "connection", "session", "http", "https", "url",
                 "endpoint", "client", "socket"):
        assert word not in segments, word
    durable = _segments(_identifiers(next(s for s in SOURCES if s.stem == "durable")))
    for word in ("http", "https", "url", "endpoint", "client", "socket"):
        assert word not in durable, word


def test_nothing_here_can_approve_compile_publish_export_authenticate_or_execute():
    """The prohibition of the ruling, over every exported type's public surface and
    over every identifier the code uses."""

    forbidden_methods = {"approve", "compile", "publish", "export", "submit", "activate",
                         "issue", "grant", "authorize", "authenticate", "execute", "run",
                         "clear", "revoke", "delete", "edit", "update", "upsert", "promote",
                         "transition", "release"}
    ruled = {"SqliteWorkflowDrafts": {"save"}}
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            methods = {n for n in dir(value) if not n.startswith("_")}
            assert not (methods & forbidden_methods), (name, methods & forbidden_methods)
            writes = methods & {"save", "record", "append", "store", "write"}
            assert writes == ruled.get(name, set()), (name, writes)
        assert name.lower() not in forbidden_methods, name
    code = _segments({n for src in SOURCES for n in _identifiers(src)})
    # ``runtime`` is not on this list only because ``RuntimeError`` and
    # ``runtime_checkable`` are stdlib names the code legitimately uses.
    for word in ("approved", "compiled", "published", "released", "authenticated",
                 "clearance", "consume", "token", "credential", "secret", "handoff"):
        assert word not in code, word
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "REFERENCE_GRADE"
    assert pkg.LIFECYCLE == "DRAFT" and pkg.CLAIMED_OWNER_ASSURANCE == "PRESENTED_UNPROVEN"


def test_the_draft_has_no_lifecycle_field_and_no_transition():
    import dataclasses

    names = {f.name for f in dataclasses.fields(pkg.WorkflowDraft)}
    for banned in ("lifecycle", "status", "state", "approved", "approval", "compiled",
                   "published", "assurance", "owner_id", "tenant_claim"):
        assert banned not in names, banned
    assert not any(isinstance(getattr(pkg.WorkflowDraft, n, None), property) and n in ("status",)
                   for n in dir(pkg.WorkflowDraft))
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert not node.name.endswith("Authority"), (src.name, node.name)
                assert "Approval" not in node.name and "Pack" not in node.name, (src.name, node.name)


def test_no_exported_name_is_an_authority_a_pack_or_a_portfolio():
    for name in pkg.__all__:
        assert not name.endswith("Authority"), name
        for word in ("Portfolio", "PolicyPack", "Approval", "Release"):
            assert word not in name, name
