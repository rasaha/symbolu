"""The package's prohibitions, made mechanical.

It records and re-arms; it never approves, authenticates, mints authority, clears or
executes. It reads no clock. Its routes carry none of the SD-2 verbs. It imports the
ratified set (HR-2) and nothing under ``packages/capabilities``.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import pytest

import ugence_governed_review_service as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED = {
    "ugence_governed_review_service", "ugence_governed_review", "ugence_approval_workflow",
    "ugence_authority_directory", "ugence_durable_execution", "ugence_governance_contracts",
    "ugence_control_plane_root", "sqlalchemy",
}
#: Presentation-only, imported inside build_app, never at module scope.
PRESENTATION = {"fastapi", "starlette"}
FORBIDDEN = {
    "ugence_agent_runtime", "ugence_agent_runtime_governance", "dbos",
    "ugence_governance_studio_api", "ugence_console_api",
    "ugence_decision_authority", "ugence_policy_workflow_compiler",
    "ugence_execution_reservation", "ugence_action_clearance", "risk_authority",
    "pydantic", "requests", "httpx", "aiohttp", "boto3", "kubernetes", "azure", "google",
    "openai", "redis", "psycopg", "jwt", "authlib", "ldap3", "msal", "oauthlib",
}
PROHIBITED_VERBS = ("grant", "approve", "authorize", "clear", "execute", "issue", "activate",
                    "revoke", "resume", "release", "continue", "signal", "retry")


def _module_scope_roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.parse(path.read_text(), filename=str(path)).body:
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _all_roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_module_scope_imports_are_the_ratified_set_and_presentation_stays_local():
    for src in SOURCES:
        strays = _module_scope_roots(src) - STDLIB - ALLOWED - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (_all_roots(src) & FORBIDDEN), (src.name, _all_roots(src) & FORBIDDEN)
        assert not (_module_scope_roots(src) & PRESENTATION), (src.name, "fastapi at module scope")
    everything = set().union(*(_all_roots(s) for s in SOURCES))
    assert "fastapi" in everything, "build_app imports the presentation layer"


def test_nothing_under_capabilities_is_imported():
    repo = DIST.parents[2]
    namespaces: set[str] = set()
    for pkg_dir in (repo / "packages" / "capabilities").iterdir():
        src_dir = pkg_dir / "src"
        if src_dir.is_dir():
            namespaces |= {p.name for p in src_dir.iterdir()
                           if p.is_dir() and not p.name.endswith(".egg-info")}
    assert namespaces, "no capability namespaces discovered; the scan is wrong"
    for src in SOURCES:
        assert not (_all_roots(src) & namespaces), (src.name, _all_roots(src) & namespaces)


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-governed-review-service"
    deps = {re.split(r"[><=]", d)[0] for d in data["project"]["dependencies"]}
    assert deps == {"ugence-governed-review", "ugence-approval-workflow",
                    "ugence-authority-directory", "ugence-durable-execution",
                    "ugence-governance-contracts", "ugence-control-plane-root", "SQLAlchemy"}
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("agent-runtime", "dbos", "pydantic", "decision-authority", "psycopg",
                      "boto3", "kubernetes", "redis", "jwt", "authlib", "ldap"):
        assert forbidden not in joined, forbidden
    assert set(data["project"]["optional-dependencies"]["http"]) == {"fastapi>=0.110", "starlette>=0.36"}
    assert pkg.__version__ == "0.3.0"


def test_no_clock_is_read_anywhere():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                    "perf_counter", "uuid4", "uuid1", "urandom", "random"), \
                    (src.name, name)
    joined = "\n".join(s.read_text() for s in SOURCES)
    assert "import time" not in joined and "datetime.now" not in joined


def test_routes_and_operation_ids_carry_no_prohibited_verb():
    """SD-2's prohibition, applied to this service's own surface: the studio's scan
    must keep passing when it relays to these paths."""

    for method, path, op_id in pkg.ROUTES:
        for verb in PROHIBITED_VERBS:
            assert verb not in path.lower(), (path, verb)
            assert not re.search(rf"(^|_){verb}", op_id.lower()), (op_id, verb)
    assert [r[0] for r in pkg.ROUTES].count("POST") == 1, "one relay route, the decision"


def test_no_surface_could_approve_authenticate_clear_or_execute():
    names = {n for n in dir(pkg.ReviewService) if not n.startswith("_")}
    assert not names & {"approve", "decide", "grant", "authenticate", "authorize", "login",
                        "sign", "execute", "dispatch", "run", "clear", "issue_credential",
                        "assume_role", "consume", "advance", "resume_workflow",
                        "continue_workflow", "release", "retry"}
    forbidden_suffixes = ("Authorization", "Grant", "Envelope", "Token", "Credential",
                          "Permit", "Client", "Session", "Principal", "Connector")
    assert [n for n in pkg.__all__ if n.endswith(forbidden_suffixes)] == []
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"
    assert pkg.IDENTITY_PROOF == "PRESENTED_UNPROVEN"


def test_no_idp_no_credential_no_network_no_live_mode():
    joined = "\n".join(s.read_text().lower() for s in SOURCES)
    for token in ("http://", "https://", "webhook", "oidc", "saml", "scim", "ldap", "bearer",
                  "jwt", "cookie", "password", "api_key", "credential_value",
                  "executionmode.live", "temporal", "langflow"):
        assert token not in joined, token


def test_the_service_resumes_only_the_instance_named_by_the_approval():
    """Every adapter call in the source passes the instance the approval binds to."""

    tree = ast.parse((PKG_DIR / "service.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("signal", "resume")
             and ast.unparse(n.func.value) == "self._adapter"]
    assert len(calls) == 2, "one signal call and one resume call"
    for call in calls:
        kw = {k.arg: ast.unparse(k.value) for k in call.keywords}
        assert kw["instance_id"] == "instance_id", kw
    resume_calls = [c for c in calls if c.func.attr == "resume"]
    assert resume_calls and all(len(c.keywords) == 1 for c in resume_calls), \
        "resume takes the instance id and nothing else: no approver, no evidence"


@pytest.mark.parametrize("token", ["MANUAL_REVIEW", "ExecutionMode", "resume_workflow"])
def test_no_new_disposition_mode_or_bare_runtime_call_is_minted(token):
    joined = "\n".join(s.read_text() for s in SOURCES)
    assert token not in joined


def test_the_service_never_appends_more_than_the_linkage_and_never_reads_the_ledger_for_meaning():
    """HE-1: one kind, one payload shape; the index reads rows by digest and nothing else."""

    tree = ast.parse((PKG_DIR / "linkage.py").read_text())
    appends = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == "append"]
    assert len(appends) == 1, "exactly one ledger append in the service"
    joined = (PKG_DIR / "linkage.py").read_text()
    assert joined.count("LedgerEntry(") == 1 and 'kind=LINKAGE_KIND' in joined
    assert "mode=ro" in joined, "the index opens the ledger read-only"
    for token in ("UPDATE ", "DELETE ", "INSERT "):
        assert token not in joined.upper().replace("UPDATE OR DELETE", ""), token
    # The whole package still makes exactly one signal and one resume call.
    svc = ast.parse((PKG_DIR / "service.py").read_text())
    calls = [n.func.attr for n in ast.walk(svc) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and ast.unparse(n.func.value) == "self._adapter"]
    assert sorted(calls) == ["resume", "signal", "status"]
