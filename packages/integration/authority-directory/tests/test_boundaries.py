"""Import boundary, the clock-free rule, the declared dependency set, the naming
prohibitions, production refusal, the absence of any authentication or custody
surface, and the append-only hash chain — asserted over source, AST and metadata.

These are the ADR's prohibitions made mechanical.
"""

from __future__ import annotations

import ast
import pathlib
import sqlite3
import sys
import tomllib

import pytest

import ugence_authority_directory as pkg
from ugence_authority_directory import (
    InMemoryAuthorityDirectory,
    ProductionModeRefused,
    RecordIntegrityError,
    SqliteAuthorityDirectory,
    StoreUnavailableError,
)

from _fixtures import T0, T1, grant, human, sqlite_directory, sqlite_path

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_authority_directory", "ugence_governance_contracts"}
FORBIDDEN = {
    # the consumers, whose ports this package satisfies without importing them
    "ugence_approval_workflow", "ugence_decision_authority", "decision_governance",
    "risk_authority", "ugence_risk_authority_runtime", "ugence_policy_authority",
    "ugence_trusted_evidence_authority", "ugence_execution_reservation", "ugence_storygraph",
    # anything an identity provider or a custody store would need
    "ldap3", "ldap", "python_ldap", "scim", "jwt", "jose", "oauthlib", "authlib",
    "cryptography", "nacl", "OpenSSL", "keyring", "hvac",
    "pydantic", "sqlalchemy", "requests", "httpx", "aiohttp", "boto3", "kubernetes",
    "azure", "google", "openai", "redis", "psycopg", "fastapi",
}


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


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_source_imports_only_stdlib_and_governance_contracts():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN), (src.name, roots & FORBIDDEN)


def test_the_consumers_ports_are_satisfied_without_importing_them():
    joined = "\n".join(src.read_text() for src in SOURCES)
    for forbidden in ("from ugence_approval_workflow", "import ugence_approval_workflow",
                      "from ugence_decision_authority", "import ugence_decision_authority",
                      "from ugence_risk_authority", "import ugence_risk_authority",
                      "from ugence_policy_authority", "import ugence_policy_authority"):
        assert forbidden not in joined


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-authority-directory"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.4.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("approval-workflow", "decision-authority", "risk-authority",
                      "policy-authority", "trusted-evidence", "pydantic", "cryptography",
                      "ldap", "boto3", "kubernetes", "sqlalchemy"):
        assert forbidden not in joined
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input, so a grant lapses without a sweeper."""

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


def test_expiry_goes_through_the_governance_contracts_validity():
    grants = (PKG_DIR / "grants.py").read_text()
    assert "from ugence_governance_contracts.api import Validity, ValidityStatus" in grants
    assert "status_at" in grants
    assert "Validity" in pkg.RoleGrant.__annotations__["validity"]


# --------------------------------------------------------------------------- #
# Naming: this package is not an Authority, and holds no trust anchor
# --------------------------------------------------------------------------- #
def test_no_exported_type_is_an_authority_or_a_trust_anchor_directory():
    for name in pkg.__all__:
        assert not name.endswith("Authority"), name
        assert not name.endswith("TrustAnchorDirectory"), name
    # Nor anywhere in the source: no class may be declared with either shape.
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert not node.name.endswith("Authority"), (src.name, node.name)
                assert not node.name.endswith("TrustAnchorDirectory"), (src.name, node.name)


def test_nothing_here_resembles_a_second_trust_anchor_directory():
    """The prose may say what the package refuses to hold; the code names none of it."""

    code = "\n".join(sorted(n for src in SOURCES for n in _identifiers(src))).lower()
    for word in ("trust_anchor", "trustanchor", "private_key", "signing_key", "keypair",
                 "password", "bearer"):
        assert word not in code, word


# --------------------------------------------------------------------------- #
# No authentication, no custody
# --------------------------------------------------------------------------- #
def test_no_adapter_authenticates_or_holds_custody_of_anything():
    from ugence_authority_directory import DirectoryApproverEligibility

    for cls in (InMemoryAuthorityDirectory, SqliteAuthorityDirectory,
                DirectoryApproverEligibility):
        names = {n for n in dir(cls) if not n.startswith("_")}
        assert not names & {
            "authenticate", "login", "logout", "verify_identity", "resolve_identity",
            "issue_token", "mint_token", "sign", "verify_signature", "credentials",
            "key", "keys", "trust_anchor", "trust_anchors", "approve", "decide",
            "authorize", "execute"}, cls.__name__
    forbidden_suffixes = ("Token", "Credential", "Key", "Secret", "Session", "Identity",
                          "Permission", "ActorType")
    assert [n for n in pkg.__all__ if n.endswith(forbidden_suffixes)] == []
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"


def test_no_answer_ever_carries_an_actor_type(tmp_path):
    """An ``ActorType`` is the IdP's output, and never this directory's."""

    directory = sqlite_directory(tmp_path)
    g = directory.put_grant(grant(human("approver-1")), as_of=T0)
    from ugence_authority_directory import projection_of

    for value in (g, g.principal, projection_of(g), g.to_dict()):
        rendered = repr(value).lower()
        assert "actortype" not in rendered and "actor_type" not in rendered
    code = {n for src in SOURCES for n in _identifiers(src)}
    assert not {n for n in code if "actortype" in n.lower() or "actor_type" in n.lower()}
    directory.close()


def test_reference_adapters_are_refused_in_production_mode(tmp_path):
    with pytest.raises(ProductionModeRefused):
        InMemoryAuthorityDirectory(production_mode=True)
    with pytest.raises(ProductionModeRefused):
        SqliteAuthorityDirectory(":memory:", production_mode=True)
    store = SqliteAuthorityDirectory(sqlite_path(tmp_path), production_mode=True)
    assert store.production_mode is True
    store.close()


# --------------------------------------------------------------------------- #
# The durable store
# --------------------------------------------------------------------------- #
def test_the_sqlite_store_uses_the_ratified_shape():
    schema = (PKG_DIR / "sqlite.py").read_text()
    assert "journal_mode=WAL" in schema and "BEGIN IMMEDIATE" in schema
    assert "directory_events_no_update" in schema and "directory_events_no_delete" in schema


def test_directory_events_are_append_only_and_hash_linked(tmp_path):
    path = sqlite_path(tmp_path)
    directory = sqlite_directory(tmp_path)
    g = directory.put_grant(grant(human("approver-1")), as_of=T0)
    directory.revoke_grant(g.grant_id, as_of=T1)
    assert directory.verify_chain()

    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("UPDATE directory_events SET event_type='GRANTED' WHERE seq=1")
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("DELETE FROM directory_events WHERE seq=1")
    # Even a privileged writer that drops the guard leaves a detectable break.
    raw.executescript("DROP TRIGGER directory_events_no_update; "
                      "UPDATE directory_events SET detail_json='{}' WHERE seq=2;")
    raw.close()
    assert directory.verify_chain() is False
    directory.close()


def test_a_tampered_grant_is_refused_on_read(tmp_path):
    path = sqlite_path(tmp_path)
    directory = sqlite_directory(tmp_path)
    g = directory.put_grant(grant(human("approver-1")), as_of=T0)
    directory.close()

    raw = sqlite3.connect(path)
    raw.execute("UPDATE grants SET record_json=replace(record_json, 'risk-approver', "
                "'super-approver') WHERE grant_id=?", (g.grant_id,))
    raw.commit()
    raw.close()

    reopened = SqliteAuthorityDirectory(path)
    with pytest.raises(RecordIntegrityError):
        reopened.get_grant(g.grant_id)
    reopened.close()


def test_schema_version_mismatch_is_refused(tmp_path):
    path = sqlite_path(tmp_path)
    SqliteAuthorityDirectory(path).close()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE meta SET value='other' WHERE key='schema_version'")
    raw.commit()
    raw.close()
    with pytest.raises(StoreUnavailableError):
        SqliteAuthorityDirectory(path)
