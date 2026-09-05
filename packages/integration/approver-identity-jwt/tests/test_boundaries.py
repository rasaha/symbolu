"""The package's prohibitions, made mechanical (adapter ADR §5).

It validates a proof it did not issue. It imports the review service, PyJWT and the
standard library and nothing else; it reads no clock; it never relaxes TLS, never
discovers an issuer, never accepts a symmetric or ``none`` algorithm, never logs,
and is not itself an issuer.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import pytest

import ugence_approver_identity_jwt as pkg
from ugence_governed_review_service import ApproverIdentityPort

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED = {"ugence_approver_identity_jwt", "ugence_governed_review_service", "jwt"}
FORBIDDEN = {
    "ugence_decision_authority", "ugence_approval_workflow", "ugence_authority_directory",
    "ugence_durable_execution", "ugence_governed_review", "ugence_control_plane_root",
    "ugence_governance_studio_api", "ugence_agent_runtime", "dbos", "sqlalchemy",
    "requests", "httpx", "aiohttp", "authlib", "jose", "msal", "oauthlib", "ldap3",
    "cryptography", "ssl", "logging", "pickle", "shelve", "sqlite3", "subprocess", "os",
}


def _roots(path: pathlib.Path, module_scope_only: bool) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    nodes = tree.body if module_scope_only else list(ast.walk(tree))
    roots = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_imports_are_the_review_service_pyjwt_and_stdlib_and_nothing_else():
    for src in SOURCES:
        strays = _roots(src, True) - STDLIB - ALLOWED - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (_roots(src, False) & FORBIDDEN), (src.name, _roots(src, False) & FORBIDDEN)
    everything = set().union(*(_roots(s, False) for s in SOURCES))
    assert "jwt" in everything and "ugence_governed_review_service" in everything


def test_nothing_under_capabilities_is_imported():
    repo = DIST.parents[2]
    namespaces: set[str] = set()
    for pkg_dir in (repo / "packages" / "capabilities").iterdir():
        src_dir = pkg_dir / "src"
        if src_dir.is_dir():
            namespaces |= {p.name for p in src_dir.iterdir()
                           if p.is_dir() and not p.name.endswith(".egg-info")}
    assert namespaces
    for src in SOURCES:
        assert not (_roots(src, False) & namespaces), src.name


def test_pyproject_declares_exactly_the_ratified_bounded_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-approver-identity-jwt"
    deps = data["project"]["dependencies"]
    names = {re.split(r"[\[><=]", d)[0] for d in deps}
    assert names == {"ugence-governed-review-service", "PyJWT", "cryptography"}
    for dep in deps:
        if dep.startswith(("PyJWT", "cryptography")):
            assert "<" in dep and ">=" in dep, f"{dep}: lower and upper bound (IA-2)"
    assert any(d.startswith("PyJWT[crypto]") for d in deps), "the crypto extra is explicit"
    assert set(data["project"].get("optional-dependencies", {})) <= {"test"}
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic", "perf_counter",
                                    "uuid4", "uuid1", "urandom", "random"), (src.name, name)
    joined = "\n".join(s.read_text() for s in SOURCES)
    assert "import time" not in joined and "datetime.now" not in joined


def test_the_algorithm_allowlist_is_asymmetric_only_and_verification_is_never_relaxed():
    assert pkg.ALGORITHMS == ("RS256", "ES256", "EdDSA")
    joined = "\n".join(s.read_text() for s in SOURCES)
    for token in ("HS256", "HS384", "HS512", '"none"', "verify_signature\": False",
                  "verify_signature': False", "_create_unverified_context", "CERT_NONE",
                  "check_hostname", "openid-configuration", ".well-known", "introspect",
                  "PyJWKClient", "print(", "logging", "leeway="):
        assert token not in joined, token
    # Every decode call verifies the signature, issuer and audience.
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "decode" and ast.unparse(node.func.value) == "jwt":
                kw = {k.arg: ast.unparse(k.value) for k in node.keywords}
                assert "algorithms" in kw and "audience" in kw and "issuer" in kw
                assert "'verify_signature': True" in kw["options"]


def test_the_package_is_not_an_issuer_and_holds_no_private_material():
    joined = "\n".join(s.read_text() for s in SOURCES)
    for token in ("HTTPServer", "BaseHTTPRequestHandler", "jwt.encode", "generate_private_key",
                  "private_bytes", "PrivateFormat", "client_secret", "password", "api_key"):
        assert token not in joined, token


def test_public_api_and_honest_labels():
    assert isinstance(pkg.JwtApproverIdentityAdapter, type)
    assert pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"
    assert pkg.ISSUER_VALIDATION == "IN_PROCESS_ISSUER_ONLY"
    assert pkg.ENFORCEMENT_ENABLED is False
    assert not hasattr(pkg.JwtApproverIdentityAdapter, "NON_PRODUCTION"), \
        "this is the real adapter; the fixture flag belongs to the static one"
    forbidden_suffixes = ("Token", "Credential", "Session", "Principal", "Client", "Issuer",
                          "Grant", "Authorization", "Envelope", "Permit", "Connector")
    assert [n for n in pkg.__all__ if n.endswith(forbidden_suffixes)] == []
    assert set(pkg.__all__) == {
        "__version__", "MATURITY", "ISSUER_VALIDATION", "ENFORCEMENT_ENABLED",
        "JwtApproverIdentityAdapter", "JwtApproverIdentity", "Refusal",
        "ALGORITHMS", "ACCESS_TOKEN_TYPES", "REQUIRED_CLAIMS",
        "AdapterConfig", "LOOPBACK_HOSTS", "JwksKeyCache", "MAX_JWKS_BYTES",
        "KeyRetrievalFailed", "AdapterConfigurationError",
    }
    assert issubclass(pkg.KeyRetrievalFailed, __import__(
        "ugence_governed_review_service").IdentityUnavailable)


def test_the_adapter_satisfies_the_port_structurally(issuer, clock):
    from conftest import config_for

    adapter = pkg.JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    assert isinstance(adapter, ApproverIdentityPort)
    names = {n for n in dir(adapter) if not n.startswith("_")}
    assert names == {"authenticate", "config", "keys", "maturity"}


@pytest.mark.parametrize("token", ["MANUAL_REVIEW", "ExecutionMode", "resume_workflow",
                                   "ExecutionMode.LIVE", "temporal", "langflow"])
def test_no_disposition_mode_runtime_call_or_prohibited_dependency_is_named(token):
    joined = "\n".join(s.read_text() for s in SOURCES)
    assert token not in joined
