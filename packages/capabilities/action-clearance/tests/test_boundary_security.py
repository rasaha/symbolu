"""Acceptance tests 57-65: boundary and security guarantees (static)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ac_helpers import ACTFP, happy_signals, policy, request, signal
from ugence_action_clearance import SignalType, ValidationError

_SRC = Path(__file__).resolve().parents[1] / "src" / "ugence_action_clearance"


def _py_files():
    return list(_SRC.rglob("*.py"))


def _imported_roots(path: Path):
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


_FORBIDDEN_ROOTS = {
    "ugence_code_governance", "symbolu_robotics", "acp",
    "ugence_decision_authority", "tap_provider", "actiongate_provider",
    "governance_providers", "ugence_governance_provider_framework",
    "ugence_storygraph", "ugence_console_api",
    "requests", "httpx", "urllib3", "sqlalchemy", "psycopg2", "sqlite3",
    "github", "kubernetes", "boto3",
}


# 57-61 & 44. no forbidden imports anywhere in the package
def test_no_forbidden_imports():
    stdlib_and_self = {"ugence_action_clearance", "__future__"}
    for p in _py_files():
        for root in _imported_roots(p):
            if root in stdlib_and_self:
                continue
            assert root not in _FORBIDDEN_ROOTS, f"{p} imports forbidden root {root}"


# 62. no new ProviderKind
def test_no_provider_kind():
    for p in _py_files():
        text = p.read_text()
        assert "ProviderKind" not in text


# 63. no persistence implementation
def test_no_persistence():
    for p in _py_files():
        text = p.read_text()
        for banned in ("sqlite3", "open(", "Repository", "def save", "def persist",
                       "def store", "SQL", "migration"):
            assert banned not in text, f"{p} contains persistence token {banned!r}"


# 64. no dispatch / execution method
def test_no_dispatch_method():
    for p in _py_files():
        text = p.read_text()
        for banned in ("def dispatch", "def execute", "def merge", "subprocess",
                       "os.system"):
            assert banned not in text, f"{p} contains execution token {banned!r}"


# 65. no reserve_once implementation
def test_no_reserve_once():
    for p in _py_files():
        text = p.read_text()
        assert "reserve_once" not in text
        assert "def reserve" not in text


def test_no_acp_namespace_or_alias():
    for p in _py_files():
        text = p.read_text()
        # bare ACP acronym must not appear in code identifiers / import aliases
        assert "autonomous_control_plane" not in text
        assert "import acp" not in text
        assert " as acp" not in text


# prohibited payloads in signals fail closed (malformed)
def test_prohibited_credential_payload_rejected(evaluator):
    bad = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP, "credential": "x"})
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), bad]
    with pytest.raises(ValidationError):
        evaluator.evaluate(request(sigs), policy())
