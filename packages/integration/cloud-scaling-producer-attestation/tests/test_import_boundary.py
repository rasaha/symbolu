"""Import and dependency boundaries — asserted over source, AST, exports and metadata.

Two directions matter, and both are checked.

**Outward:** this package must not import Policy Authority, Decision Authority, ActionGate,
the Credential Broker, Cloud Scaling Operations, a cloud SDK, an execution-assurance or
learning package, the Cloud Scaling **Controller**, or any private symbol of any dependency.

**Inward:** nothing upstream may take on a dependency on this package. The Controller in
particular stays a key-free advisory leaf at 0.4.0: it declares no dependency here, and no
module of it is imported here.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from _producer_fixtures import repo_root as _repo_root

import ugence_cloud_scaling_producer_attestation as pkg

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
REPO = _repo_root()
PYPROJECT = PKG_DIR.parents[1] / "pyproject.toml"
SOURCES = sorted(PKG_DIR.rglob("*.py"))

#: The exact dependency set ratified for Phase 5B-0A. Three first-party packages.
ALLOWED_FIRST_PARTY = {
    "risk_authority",
    "ugence_trusted_evidence_authority",
    "ugence_cloud_scaling_authorization_contracts",
}

#: Every distribution and module this package may never reach.
FORBIDDEN_ROOTS = {
    "ugence_policy_authority",
    "ugence_decision_authority",
    "ugence_actiongate_provider",
    "ugence_cloud_scaling_operations",
    "ugence_cloud_scaling_controller",
    "ugence_risk_authority_execution_assurance",
    "ugence_risk_authority_runtime_assurance",
    "boto3",
    "kubernetes",
    "azure",
    "google",
    "openai",
}

#: Forbidden Risk Authority sub-modules — the authority surface, as distinct from crypto.
FORBIDDEN_RA_MODULES = {
    "risk_authority.services",
    "risk_authority.integrations.actiongate",
    "risk_authority.domain.envelope",
    "risk_authority.domain.actions",
    "risk_authority.api",
}


def _imports():
    """Every absolute import in the package, as ``(file, module)`` pairs."""

    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield path.name, alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path.name, node.module


# --------------------------------------------------------------------------------------- #
# Outward
# --------------------------------------------------------------------------------------- #


def test_no_forbidden_distribution_is_imported():
    """B-1: no policy, decision, gate, credential, operations, SDK or controller import."""

    offenders = [
        f"{file}: {module}"
        for file, module in _imports()
        if module.split(".")[0] in FORBIDDEN_ROOTS
    ]
    assert offenders == [], offenders


def test_no_risk_authority_authority_surface_is_imported():
    """B-2: Risk Authority is reached for canonicalization only, never for authority."""

    offenders = []
    for file, module in _imports():
        for forbidden in FORBIDDEN_RA_MODULES:
            if module == forbidden or module.startswith(forbidden + "."):
                offenders.append(f"{file}: {module}")
    assert offenders == [], offenders


def test_risk_authority_is_reached_only_through_its_public_crypto_api():
    """B-3: only ``risk_authority.crypto.canonical`` and ``.hashing``, and only their
    public exports."""

    import risk_authority.crypto.canonical as ra_canonical
    import risk_authority.crypto.hashing as ra_hashing

    reached = {module for _, module in _imports() if module.startswith("risk_authority")}
    assert reached <= {"risk_authority.crypto.canonical", "risk_authority.crypto.hashing"}

    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module == "risk_authority.crypto.canonical":
                for alias in node.names:
                    assert alias.name in ra_canonical.__all__, alias.name
            if node.module == "risk_authority.crypto.hashing":
                for alias in node.names:
                    assert alias.name in ra_hashing.__all__, alias.name


def test_the_trusted_evidence_authority_is_reached_only_through_its_curated_api():
    """B-4: TEV's trust primitives, via its top-level curated API. No private symbol."""

    import ugence_trusted_evidence_authority as tev

    reached = {
        module
        for _, module in _imports()
        if module.startswith("ugence_trusted_evidence_authority")
    }
    assert reached == {"ugence_trusted_evidence_authority"}, reached

    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "ugence_trusted_evidence_authority"
            ):
                for alias in node.names:
                    assert alias.name in tev.__all__, alias.name


def test_phase_5a_is_reached_only_through_its_public_api():
    """B-5: the Phase 5A candidate is consumed read-only, through its curated exports."""

    import ugence_cloud_scaling_authorization_contracts as p5a

    reached = {
        module
        for _, module in _imports()
        if module.startswith("ugence_cloud_scaling_authorization_contracts")
    }
    assert reached == {"ugence_cloud_scaling_authorization_contracts"}, reached

    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "ugence_cloud_scaling_authorization_contracts"
            ):
                for alias in node.names:
                    assert alias.name in p5a.__all__, alias.name


def test_no_private_symbol_of_any_dependency_is_imported():
    """B-6: no ``_``-prefixed name is imported from any third-party or sibling module."""

    offenders = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or not node.module:
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    offenders.append(f"{path.name}: {node.module}.{alias.name}")
    assert offenders == [], offenders


@pytest.mark.invariant
def test_the_declared_dependencies_are_exactly_the_ratified_three():
    """B-7: the manifest names exactly the three ratified first-party dependencies."""

    text = PYPROJECT.read_text(encoding="utf-8")
    block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = {
        line.strip().strip('",').split(">=")[0].split("==")[0]
        for line in block.strip().splitlines()
        if line.strip().startswith('"')
    }
    assert declared == {
        "ugence-risk-authority",
        "ugence-trusted-evidence-authority",
        "ugence-cloud-scaling-authorization-contracts",
    }, declared


def test_no_forbidden_distribution_is_declared_as_a_dependency():
    """B-8: no policy, gate, credential, operations, SDK or controller distribution."""

    text = PYPROJECT.read_text(encoding="utf-8").lower()
    block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    for forbidden in (
        "policy-authority",
        "decision-authority",
        "actiongate",
        "credential",
        "cloud-scaling-operations",
        "cloud-scaling-controller",
        "execution-assurance",
        "boto3",
        "kubernetes",
    ):
        assert forbidden not in block, forbidden


# --------------------------------------------------------------------------------------- #
# Inward — the Controller gains nothing
# --------------------------------------------------------------------------------------- #


def test_the_controller_declares_no_dependency_on_this_package():
    """B-9: the Cloud Scaling Controller stays a key-free advisory leaf."""

    controller_pyproject = (
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "pyproject.toml"
    )
    text = controller_pyproject.read_text(encoding="utf-8")
    assert "ugence-cloud-scaling-producer-attestation" not in text
    assert "ugence_cloud_scaling_producer_attestation" not in text


def test_no_controller_module_is_imported_here():
    """B-10: the attestation is produced AT the controller boundary, never BY it."""

    for file, module in _imports():
        assert not module.startswith("ugence_cloud_scaling_controller"), f"{file}: {module}"


def test_no_upstream_package_imports_this_one():
    """B-11: this is a one-way leaf. No dependency of it may depend back on it."""

    upstream = (
        REPO / "packages" / "risk_authority" / "src",
        REPO / "packages" / "trusted-evidence-authority" / "src",
        REPO
        / "packages"
        / "integration"
        / "cloud-scaling-authorization-contracts"
        / "src",
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
    )
    offenders = []
    for root in upstream:
        for path in root.rglob("*.py"):
            if "ugence_cloud_scaling_producer_attestation" in path.read_text(
                encoding="utf-8"
            ):
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], offenders


# --------------------------------------------------------------------------------------- #
# No authority vocabulary in the public surface
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fragment",
    ["envelope", "actiongate", "action_gate", "credential", "executor", "execute",
     "authorize", "authorization", "admit", "clock"],
)

def test_no_public_export_names_an_authority_or_execution_concept(fragment):
    """B-12: the curated API contains no word for a capability this phase does not have."""

    offenders = [s for s in pkg.__all__ if fragment in s.lower()]
    assert offenders == [], offenders


def test_no_source_defines_an_envelope_gate_credential_or_executor_symbol():
    """B-13: and neither does any module-level definition inside the package."""

    banned = ("envelope", "actiongate", "credential", "executor")
    offenders = []
    for path, in ((p,) for p in SOURCES):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            name = getattr(node, "name", None)
            if name and any(b in name.lower() for b in banned):
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], offenders
