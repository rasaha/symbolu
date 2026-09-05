"""Import and dependency boundaries — asserted over source, AST, exports and metadata."""

from __future__ import annotations

import ast
import pathlib
import re

import ugence_cloud_scaling_credential_broker as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
SOURCES = sorted(PKG_DIR.rglob("*.py"))

ALLOWED_FIRST_PARTY = {
    "risk_authority", "ugence_cloud_scaling_authorization_contracts", "ugence_cloud_scaling_action_admission",
    "ugence_execution_reservation", "ugence_governance_contracts",
}
ALLOWED_STDLIB = {"__future__", "dataclasses", "datetime", "enum", "re", "typing"}
BANNED_ENVIRONMENT = {"os", "sys", "secrets", "socket", "time", "subprocess", "urllib", "http", "pathlib",
                      "random", "ssl", "asyncio", "threading", "multiprocessing", "ctypes", "platform"}
BANNED_CLOUD = {"boto3", "botocore", "kubernetes", "azure", "google", "oci", "hvac", "requests", "httpx",
                "aiohttp", "ugence_cloud_scaling_operations", "ugence_cloud_scaling_controller",
                "ugence_trusted_evidence_authority", "ugence_policy_authority", "ugence_action_clearance",
                "ugence_cloud_scaling_envelope_issuance", "ugence_cloud_scaling_policy_authenticity",
                "ugence_cloud_scaling_producer_attestation"}
FORBIDDEN_RA_MODULES = {"risk_authority.crypto.signing", "risk_authority.crypto.keys", "risk_authority.services",
                        "risk_authority.api.dependencies", "risk_authority.persistence",
                        "risk_authority.integrations"}
FORBIDDEN_CALLS = {"authorize_action", "issue_envelope", "reserve_once", "mark_dispatched", "release",
                   "sign", "verify", "put_receipt", "revoke_receipt", "advance_epoch"}


def _imports():
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield path.name, alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path.name, node.module


def test_every_absolute_import_is_ratified():
    offenders = [(f, m) for f, m in _imports() if m.split(".")[0] not in ALLOWED_FIRST_PARTY | ALLOWED_STDLIB]
    assert offenders == []


def test_no_environment_network_or_cloud_module_is_imported():
    offenders = [(f, m) for f, m in _imports() if m.split(".")[0] in BANNED_ENVIRONMENT | BANNED_CLOUD]
    assert offenders == []


def test_no_risk_authority_authority_surface_is_imported():
    offenders = [(f, m) for f, m in _imports()
                 if any(m == fm or m.startswith(fm + ".") for fm in FORBIDDEN_RA_MODULES)]
    assert offenders == []


def test_no_call_lifts_containment_mutates_the_ledger_or_signs():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALLS:
                offenders.append(f"{path.name}: .{node.func.attr}()")
    assert offenders == []


def test_no_dynamic_import_exists():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for banned in ("__import__", "importlib", "find_spec"):
            assert banned not in text, (path.name, banned)


def test_declared_dependencies_equal_the_ratified_set():
    text = PYPROJECT.read_text(encoding="utf-8")
    block = text[text.index("dependencies = ["):]
    block = block[: block.index("]")]
    declared = {re.split(r"[<>=]", line.strip().strip('",'))[0] for line in block.splitlines()[1:]
                if line.strip().startswith('"')}
    assert declared == {"ugence-risk-authority", "ugence-cloud-scaling-authorization-contracts",
                        "ugence-cloud-scaling-action-admission", "ugence-execution-reservation",
                        "ugence-governance-contracts"}
    assert "ugence-risk-authority>=0.8.0" in text
    for sdk in ("boto3", "kubernetes", "azure", "google", "hvac", "requests"):
        assert sdk not in block.lower()


def test_no_upstream_package_imports_this_one():
    repo = PROJECT.parents[1]
    upstream = [repo / "risk_authority" / "src", repo / "integration" / "cloud-scaling-action-admission" / "src",
                repo / "integration" / "execution-reservation" / "src", repo / "governance-contracts" / "src"]
    offenders = [str(p) for root in upstream if root.exists() for p in root.rglob("*.py")
                 if "ugence_cloud_scaling_credential_broker" in p.read_text(encoding="utf-8")]
    assert offenders == []


def test_the_public_surface_exports_no_execution_vocabulary():
    banned = {"executable", "execute", "dispatch", "actuate", "kubeconfig", "secret"}
    assert not {name for name in pkg.__all__ if name.lower() in banned}
