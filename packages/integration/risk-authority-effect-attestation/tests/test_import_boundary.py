"""Import and dependency boundaries, asserted over source, AST and metadata.

Outward: only the standard library, ``ugence_governance_contracts`` and the
exact Trusted Evidence Authority grant. Never RA-8, Decision Authority, Agent
Runtime, any Risk Authority runtime, Policy Authority, a Benchmark Registry
package, a cloud SDK, or a cryptographic library directly.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tomllib

import ugence_risk_authority_effect_attestation as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {
    "ugence_risk_authority_effect_attestation",
    "ugence_governance_contracts",
    "ugence_trusted_evidence_authority",
}
FORBIDDEN = {
    "ugence_risk_authority_execution_assurance", "ugence_risk_authority_runtime",
    "ugence_risk_authority_evidence_runtime", "ugence_risk_authority_status_runtime",
    "ugence_risk_authority_runtime_assurance", "risk_authority",
    "ugence_decision_authority", "ugence_agent_runtime", "ugence_policy_authority",
    "ugence_benchmark_registry", "ugence_benchmark_registry_authority",
    "ugence_cloud_scaling_producer_attestation", "ugence_governance_provider_framework",
    "ugence_actiongate_provider", "ugence_approval_workflow",
    "cryptography", "nacl", "OpenSSL", "Crypto", "ed25519", "pydantic", "requests", "httpx",
    "boto3", "kubernetes", "azure", "google", "os", "pathlib", "socket", "ssl", "secrets",
    "random", "subprocess", "urllib", "http", "asyncio", "threading",
}
#: The exact TEA symbols the consumer grant permits production source to import.
TEA_GRANT = {
    "TrustAnchorCoordinate", "TrustAnchorRecord", "TrustAnchorCapability",
    "TrustAnchorResolution", "TrustAnchorResolverPort", "KeyRevocation",
    "DenyAllTrustAnchorDirectory", "StaticTrustAnchorDirectory",
    "TrustedEvidenceSigningKey", "TrustedEvidenceVerificationKey",
    "encode_public_key", "encode_signature", "decode_signature",
    "TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1", "TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1",
    "TrustedEvidenceRefusalReason",
}


def _imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, None
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module, [a.name for a in node.names]


def test_source_imports_only_stdlib_governance_contracts_and_the_tea_grant():
    for src in SOURCES:
        for module, names in _imports(src):
            root = module.split(".")[0]
            assert root in STDLIB or root in ALLOWED_FIRST_PARTY or root == "__future__", (src.name, module)
            assert root not in FORBIDDEN, (src.name, module)
            if root == "ugence_trusted_evidence_authority":
                assert module == root, (src.name, module, "only the curated top level")
                assert names is not None and "*" not in names, (src.name, "no module binding, no star")
                assert set(names) <= TEA_GRANT, (src.name, set(names) - TEA_GRANT)
            if root == "ugence_governance_contracts":
                assert names is not None and set(names) <= {
                    "ExecutionObservation", "ExecutionBusinessOutcome"}, (src.name, names)


def test_pyproject_declares_exactly_the_two_ratified_dependencies():
    data = tomllib.loads((DIST / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "ugence-risk-authority-effect-attestation"
    assert data["project"]["dependencies"] == [
        "ugence-governance-contracts>=0.8.0",
        "ugence-trusted-evidence-authority>=0.5.0",
    ]
    assert pkg.__version__ == "0.2.0"


def test_the_package_does_not_touch_execution_observation_itself():
    """SE-3: governance-contracts is wrapped, never modified. The only thing this
    package does with the observation class is hold it by exact type."""

    from ugence_governance_contracts import ExecutionObservation

    import dataclasses

    assert [f.name for f in dataclasses.fields(ExecutionObservation)] == [
        "business_outcome", "observed_parameters", "final", "reason", "provider_trace_id", "fingerprint",
    ]
    for src in SOURCES:
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    assert getattr(base, "id", getattr(base, "attr", "")) != "ExecutionObservation", (
                        src.name, node.name)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setattr":
                raise AssertionError(f"{src.name}: setattr on foreign objects is forbidden")


def test_no_module_name_or_exported_name_claims_a_capability_this_slice_does_not_ship():
    module_names = {src.stem for src in SOURCES}
    for banned in ("gateway", "connector", "reconcil", "ingress", "store", "directory", "adapter",
                   "kms", "hsm", "client", "loader", "discovery", "credential"):
        assert not any(banned in m for m in module_names), banned
    for symbol in pkg.__all__:
        for banned in ("Gateway", "Connector", "Reconcil", "Ingress", "Store", "Kms", "Hsm",
                       "Client", "Loader", "Discovery", "Credential", "Admission"):
            assert banned not in symbol, symbol
