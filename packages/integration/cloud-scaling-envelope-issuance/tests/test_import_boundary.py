"""Import and capability boundaries — asserted over source, AST, exports and metadata.

Outward: only the five ratified first-party roots, and none of Risk Authority's contained
surfaces (ActionGate, the issuer, keys). Inward: none of the five imports this package.
"""

from __future__ import annotations

import ast
import pathlib
import re

import ugence_cloud_scaling_envelope_issuance as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
SOURCES = sorted(PKG_DIR.rglob("*.py"))

ALLOWED_FIRST_PARTY = {
    "risk_authority",
    "ugence_cloud_scaling_authorization_contracts",
    "ugence_cloud_scaling_policy_authenticity",
    "ugence_cloud_scaling_producer_attestation",
    "ugence_policy_authority",
}
ALLOWED_STDLIB = {"__future__", "dataclasses", "datetime", "enum", "typing"}
FORBIDDEN_ROOTS = {
    "ugence_cloud_scaling_controller", "ugence_cloud_scaling_risk_integration",
    "ugence_cloud_scaling_operations", "ugence_decision_authority", "ugence_actiongate_provider",
    "ugence_trusted_evidence_authority", "ugence_risk_authority_execution_assurance",
    "ugence_risk_authority_runtime_assurance", "boto3", "kubernetes", "azure", "google",
    "time", "calendar", "random", "secrets", "os", "subprocess", "socket", "http", "urllib",
}
#: Risk Authority surfaces this package must reach only through the seam, or never.
FORBIDDEN_RA_MODULES = {
    "risk_authority.integrations", "risk_authority.services.envelope_issuer",
    "risk_authority.services.envelope_verifier", "risk_authority.services.decision_authority",
    "risk_authority.crypto.signing", "risk_authority.domain.actions", "risk_authority.api.dependencies",
}
#: Attribute calls that would mean lifting containment or minting authority here.
FORBIDDEN_CALLS = {
    "authorize_action", "issue_envelope", "issue_decision", "create_case", "evaluate_case",
    "sign", "from_seed", "generate", "next",
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


def test_no_call_mints_authority_signs_or_lifts_containment():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_CALLS:
                    offenders.append(f"{path.name}: .{node.func.attr}()")
    assert offenders == []


def test_no_source_names_a_key_seed_or_signature_primitive():
    pattern = re.compile(r"\b(SigningKey\b|from_seed|private_key|seed=|nacl|cryptography)\b")
    offenders = [p.name for p in SOURCES if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_declared_dependencies_equal_the_ratified_set():
    text = PYPROJECT.read_text(encoding="utf-8")
    block = text[text.index("dependencies = ["):]
    block = block[: block.index("]")]
    declared = {re.split(r"[<>=]", line.strip().strip('",'))[0] for line in block.splitlines()[1:]
                if line.strip().startswith('"')}
    assert declared == {
        "ugence-risk-authority", "ugence-cloud-scaling-authorization-contracts",
        "ugence-cloud-scaling-policy-authenticity", "ugence-cloud-scaling-producer-attestation",
        "ugence-policy-authority",
    }
    assert "ugence-risk-authority>=0.6.0" in text


def test_no_upstream_package_imports_this_one():
    repo = PROJECT.parents[1]
    upstream = [
        repo / "risk_authority" / "src",
        repo / "policy-authority" / "src",
        repo / "integration" / "cloud-scaling-authorization-contracts" / "src",
        repo / "integration" / "cloud-scaling-policy-authenticity" / "src",
        repo / "integration" / "cloud-scaling-producer-attestation" / "src",
    ]
    offenders = [str(p) for root in upstream if root.exists() for p in root.rglob("*.py")
                 if "ugence_cloud_scaling_envelope_issuance" in p.read_text(encoding="utf-8")]
    assert offenders == []


def test_the_public_surface_exports_no_authority_vocabulary():
    banned = {"authorized", "executable", "credential", "actuate", "execute"}
    assert not {name for name in pkg.__all__ if name.lower() in banned}
