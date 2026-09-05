"""The package's prohibitions, made mechanical.

It composes; it never approves, authenticates, mints authority, signals, resumes or
executes. It reads no clock. Its import graph is the ratified one (HR-2): the
approval ledger, the authority directory, the governance contracts it must produce,
and nothing under ``packages/capabilities``, no product, no network client.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tomllib

import pytest

import ugence_governed_review as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {
    "ugence_governed_review",
    "ugence_approval_workflow",
    "ugence_authority_directory",
    "ugence_agent_runtime_governance",
    "ugence_risk_authority_runtime",
    "ugence_governance_contracts",
}
FORBIDDEN = {
    # the engine, the runtime and the studio: composed around, never imported here
    "ugence_durable_execution", "dbos", "ugence_agent_runtime",
    "ugence_governance_studio_api", "ugence_console_api",
    # capabilities and reserved nouns
    "ugence_decision_authority", "ugence_policy_workflow_compiler",
    "ugence_execution_reservation", "ugence_action_clearance", "risk_authority",
    # everything a binding has no business reaching for
    "pydantic", "sqlalchemy", "requests", "httpx", "aiohttp", "boto3", "kubernetes",
    "azure", "google", "openai", "redis", "psycopg", "fastapi",
}


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_source_imports_only_the_ratified_set():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN), (src.name, roots & FORBIDDEN)


def test_nothing_under_capabilities_is_imported():
    """Every namespace a capability package ships stays out of this package's imports."""

    repo = DIST.parents[2]
    namespaces: set[str] = set()
    for pkg_dir in (repo / "packages" / "capabilities").iterdir():
        src_dir = pkg_dir / "src"
        if src_dir.is_dir():
            namespaces |= {p.name for p in src_dir.iterdir() if p.is_dir() and not p.name.endswith(".egg-info")}
    assert namespaces, "no capability namespaces discovered; the scan is wrong"
    for src in SOURCES:
        assert not (_roots(src) & namespaces), (src.name, _roots(src) & namespaces)


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-governed-review"
    deps = {d.split(">=")[0] for d in data["project"]["dependencies"]}
    assert deps == {
        "ugence-approval-workflow", "ugence-authority-directory",
        "ugence-agent-runtime-governance", "ugence-risk-authority-runtime",
        "ugence-governance-contracts",
    }
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("durable-execution", "dbos", "pydantic", "decision-authority",
                      "sqlalchemy", "psycopg", "boto3", "kubernetes", "redis"):
        assert forbidden not in joined
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant comes from the injected clock; the package never asks the host."""

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


def test_no_surface_could_approve_signal_resume_or_execute():
    names = {n for n in dir(pkg.ApprovalBoundInputSource) if not n.startswith("_")}
    assert not names & {"approve", "decide", "grant", "authenticate", "authorize", "sign",
                        "execute", "dispatch", "run", "signal", "resume", "advance",
                        "continue_workflow", "resume_workflow", "issue_credential",
                        "assume_role", "notify", "push"}
    forbidden_suffixes = ("Authorization", "Grant", "Envelope", "Token", "Credential",
                          "Permit", "Client", "Mirror", "Connector")
    assert [n for n in pkg.__all__ if n.endswith(forbidden_suffixes)] == []
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"


def test_no_network_no_credential_no_live_mode():
    joined = "\n".join(s.read_text().lower() for s in SOURCES)
    for token in ("http://", "https://", "webhook", "servicenow", "jira",
                  "executionmode.live", "credential_value", "password", "api_key"):
        assert token not in joined, token


def test_the_source_never_widens_beyond_the_decision_authority_hold():
    """The only field a consumed approval may change is the DA veto and its labels."""

    from dataclasses import fields

    from ugence_risk_authority_runtime.contracts import GovernanceRestrictions

    tree = ast.parse((PKG_DIR / "source.py").read_text())
    replaces = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "replace"]
    assert replaces, "the release goes through dataclasses.replace; none found"
    seen_targets = set()
    for call in replaces:
        target = ast.unparse(call.args[0])
        keywords = {k.arg for k in call.keywords}
        seen_targets.add(target)
        if target == "da.restrictions":
            assert keywords == {"required_approvals"}, keywords
        elif target == "da":
            assert keywords <= {"disposition", "reason_codes", "restrictions"}, keywords
        elif target == "upstream":
            assert keywords == {"decision_authority"}, keywords
        else:
            raise AssertionError(f"unexpected replace target {target}")
    assert {"da.restrictions", "da", "upstream"} <= seen_targets
    untouched = {f.name for f in fields(GovernanceRestrictions)} - {"required_approvals"}
    for call in replaces:
        assert not ({k.arg for k in call.keywords} & untouched), "a restriction was rewritten"


def test_the_hook_protocol_is_satisfied_structurally(tmp_path):
    from ugence_agent_runtime_governance import GovernanceInputSource

    import _fixtures as F

    src = F.source(F.sqlite_ledger(tmp_path), F.Clock())
    assert isinstance(src, GovernanceInputSource)


@pytest.mark.parametrize("token", ["MANUAL_REVIEW", "ExecutionMode"])
def test_no_new_disposition_or_mode_is_minted(token):
    joined = "\n".join(s.read_text() for s in SOURCES)
    assert token not in joined
