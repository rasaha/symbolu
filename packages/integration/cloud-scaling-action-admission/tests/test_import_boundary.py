"""Import and capability boundaries — asserted over source, AST, exports and metadata."""

from __future__ import annotations

import ast
import pathlib
import re

import ugence_cloud_scaling_action_admission as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
SOURCES = sorted(PKG_DIR.rglob("*.py"))

ALLOWED_FIRST_PARTY = {
    "risk_authority",
    "ugence_cloud_scaling_authorization_contracts",
    "ugence_cloud_scaling_envelope_issuance",
}
ALLOWED_STDLIB = {"__future__", "dataclasses", "datetime", "typing"}
FORBIDDEN_ROOTS = {
    "ugence_cloud_scaling_controller", "ugence_cloud_scaling_risk_integration",
    "ugence_cloud_scaling_operations", "ugence_cloud_scaling_policy_authenticity",
    "ugence_cloud_scaling_producer_attestation", "ugence_policy_authority", "ugence_decision_authority",
    "ugence_actiongate_provider", "ugence_trusted_evidence_authority", "ugence_execution_reservation",
    "ugence_action_clearance", "boto3", "kubernetes", "azure", "google", "time", "os", "subprocess",
    "socket", "http", "urllib", "random", "secrets", "hashlib",
}
#: Risk Authority surfaces this package must never touch: signing, verification, the issuer,
#: the application internals and the legacy authorization path.
FORBIDDEN_RA_MODULES = {
    "risk_authority.crypto.signing", "risk_authority.services.envelope_issuer",
    "risk_authority.services.envelope_verifier", "risk_authority.services.envelope_signer",
    "risk_authority.services.decision_authority", "risk_authority.api.dependencies",
    "risk_authority.persistence",
}
FORBIDDEN_CALLS = {
    "authorize_action", "issue_envelope", "issue_decision", "create_case", "sign", "verify",
    "advance_epoch", "revoke_envelope", "next", "save",
}


def _imports():
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield path.name, alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path.name, node.module


def test_every_absolute_import_is_ratified():
    offenders = [(f, m) for f, m in _imports()
                 if m.split(".")[0] not in ALLOWED_FIRST_PARTY | ALLOWED_STDLIB]
    assert offenders == []


def test_no_forbidden_root_or_risk_authority_surface_is_imported():
    offenders = [(f, m) for f, m in _imports()
                 if m.split(".")[0] in FORBIDDEN_ROOTS
                 or any(m == fm or m.startswith(fm + ".") for fm in FORBIDDEN_RA_MODULES)]
    assert offenders == []


def test_no_call_verifies_signs_mutates_or_lifts_containment():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_CALLS:
                    offenders.append(f"{path.name}: .{node.func.attr}()")
    assert offenders == []


def test_the_gate_never_touches_the_key_ring_or_revocation_it_is_handed():
    src = (PKG_DIR / "gate.py").read_text(encoding="utf-8")
    body = src.split("def authorize(")[1]
    assert "key_ring." not in body and "revocation_state." not in body


def test_declared_dependencies_equal_the_ratified_set():
    text = PYPROJECT.read_text(encoding="utf-8")
    block = text[text.index("dependencies = ["):]
    block = block[: block.index("]")]
    declared = {re.split(r"[<>=]", line.strip().strip('",'))[0] for line in block.splitlines()[1:]
                if line.strip().startswith('"')}
    assert declared == {"ugence-risk-authority", "ugence-cloud-scaling-authorization-contracts",
                        "ugence-cloud-scaling-envelope-issuance"}
    assert "ugence-risk-authority>=0.8.0" in text


def test_no_upstream_package_imports_this_one():
    repo = PROJECT.parents[1]
    upstream = [repo / "risk_authority" / "src",
                repo / "integration" / "cloud-scaling-authorization-contracts" / "src",
                repo / "integration" / "cloud-scaling-envelope-issuance" / "src"]
    offenders = [str(p) for root in upstream if root.exists() for p in root.rglob("*.py")
                 if "ugence_cloud_scaling_action_admission" in p.read_text(encoding="utf-8")]
    assert offenders == []


def test_the_public_surface_exports_no_execution_vocabulary():
    banned = {"executable", "credential", "actuate", "execute", "dispatch"}
    assert not {name for name in pkg.__all__ if name.lower() in banned}
