"""The dependency direction and the forbidden-import boundary.

Phase 5A may reach exactly three first-party packages, and only their public contracts.
Everything that could confer authority — Decision Authority, the envelope issuer,
ActionGate, Policy Authority internals, TEV internals, any Credential Broker, Cloud
Scaling Operations, a cloud SDK, a Kubernetes client — is absent from the import graph, and
this module proves absence by reading the source rather than by observing that today's
inputs happened not to reach one.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import pkgutil

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg

SRC = pathlib.Path(pkg.__file__).resolve().parent


def package_modules():
    for info in pkgutil.iter_modules(pkg.__path__):
        yield __import__(f"{pkg.__name__}.{info.name}", fromlist=["_"])


def all_source_files():
    return sorted(SRC.rglob("*.py"))


def imported_names(module):
    """Absolute imported module names only.

    Relative imports (``from .errors import ...``) carry ``level > 0`` and name a sibling
    inside this package, so they are excluded — they are not a reach outside the boundary.
    """

    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


FORBIDDEN_IMPORT_PREFIXES = (
    # --- authority ---
    "ugence_decision_authority",
    "ugence_actiongate_provider",
    "risk_authority.services.envelope_issuer",
    "risk_authority.services.envelope_verifier",
    "risk_authority.integrations.actiongate",
    "risk_authority.api.actiongate",
    # --- policy / evidence implementations ---
    "ugence_policy_authority",
    "ugence_trusted_evidence_authority",
    # --- execution ---
    "ugence_cloud_scaling_operations",
    "kubernetes",
    "boto3",
    "botocore",
    "google.cloud",
    "azure",
    # --- transport / process ---
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
    # --- clocks ---
    "time",
)

#: Substrings that must not appear as an imported name anywhere. Credential brokerage has
#: no single canonical module name, so it is matched by name fragment.
FORBIDDEN_NAME_FRAGMENTS = (
    "credential_broker",
    "credentialbroker",
    "actiongate",
    "envelope_issuer",
)


def test_no_module_imports_a_forbidden_dependency():
    for module in package_modules():
        for name in imported_names(module):
            for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                assert not (name == forbidden or name.startswith(forbidden + ".")), (
                    f"{module.__name__} imports {name}, which reaches {forbidden}"
                )
            lowered = name.lower()
            for fragment in FORBIDDEN_NAME_FRAGMENTS:
                assert fragment not in lowered, (
                    f"{module.__name__} imports {name}, matching forbidden fragment "
                    f"{fragment!r}"
                )


def test_only_the_three_permitted_first_party_packages_are_imported():
    permitted_roots = {
        "risk_authority",
        "ugence_cloud_scaling_controller",
        "ugence_cloud_scaling_risk_integration",
        "ugence_cloud_scaling_authorization_contracts",
    }
    stdlib_ok = {
        "__future__", "dataclasses", "datetime", "enum", "typing", "re", "unicodedata",
    }
    for module in package_modules():
        for name in imported_names(module):
            root = name.split(".")[0]
            assert root in permitted_roots | stdlib_ok, (
                f"{module.__name__} imports {name}; Phase 5A may reach only "
                f"{sorted(permitted_roots)} plus the standard library"
            )


def test_no_reference_grade_production_substitute_is_imported():
    """Reference substitutes are for test composition, never for a contract package."""

    forbidden = (
        "ReferenceActionGate",
        "ReferenceDecisionAuthority",
        "ReferenceEvidenceAdmission",
        "ReferenceAuthorityVerifier",
        "ReferenceSubjectAwarePolicyResolver",
        "RiskEvaluationSeam",
    )
    for path in all_source_files():
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        for name in forbidden:
            assert name not in imported, f"{path.name} imports {name}"


def test_no_private_symbol_is_imported_from_a_dependency():
    """A private symbol is a missing public contract, not something to reach around."""

    for path in all_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                for alias in node.names:
                    assert not alias.name.startswith("_"), (
                        f"{path.name} imports the private symbol {alias.name} from "
                        f"{node.module}; Phase 5A must stop and report a missing public "
                        "contract instead"
                    )


def test_declared_dependencies_match_the_import_graph():
    pyproject = (SRC.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    for expected in (
        "ugence-cloud-scaling-controller",
        "ugence-risk-authority",
        "ugence-cloud-scaling-risk-integration",
    ):
        assert expected in pyproject
    for forbidden in (
        "ugence-policy-authority",
        "ugence-decision-authority",
        "ugence-actiongate-provider",
        "ugence-cloud-scaling-operations",
        "ugence-trusted-evidence-authority",
        "boto3",
        "kubernetes",
        "cryptography",
    ):
        assert forbidden not in pyproject, f"{forbidden} is declared as a dependency"


def test_no_dependency_imports_this_package():
    """The leaf direction: nothing upstream may depend on Phase 5A."""

    repo = SRC.parents[4]
    roots = [
        repo / "packages" / "risk_authority" / "src",
        repo / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
        repo / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
    ]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "ugence_cloud_scaling_authorization_contracts" not in text, (
                f"{path} imports Phase 5A, creating a dependency cycle"
            )
