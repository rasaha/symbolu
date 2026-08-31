"""BR-1 stops where the ADR says it stops (ADR §30, §32).

Structural proof that no BR-2, UVI-EV-1/M-3R.4 or GV-* capability leaked into
this milestone, that BR-1 shipped the contract layer §30 assigns it and nothing
beyond, and that no placeholder, stub or reserved field stands in for a later
milestone. A milestone boundary asserted only in prose is not a boundary.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import pathlib

import pytest
import ugence_benchmark_registry
from ugence_benchmark_registry import api

PKG_ROOT = pathlib.Path(ugence_benchmark_registry.__file__).resolve().parent


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def _defined_class_names():
    names = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
    return names


def _defined_function_names():
    names = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
    return names


def test_the_package_version_is_the_first_br1_version():
    assert ugence_benchmark_registry.__version__ == "0.1.0"
    assert api.__version__ == "0.1.0"


def test_no_separate_contract_version_constant_is_minted():
    """``CONTRACT_VERSION`` is the *provider* convention in this repository.

    The contract-shape packages — ``ugence-governance-contracts``,
    ``ugence-uvi-policy-contracts``, ``ugence-policy-authority``,
    ``ugence-trusted-evidence-authority`` — carry only ``__version__``. BR-1
    follows the contract-shape convention rather than inventing a constant for
    symmetry. The versioning that *is* load-bearing is bound into every digest.
    """

    assert not hasattr(ugence_benchmark_registry, "CONTRACT_VERSION")
    assert "CONTRACT_VERSION" not in api.__all__
    assert api.BENCHMARK_REGISTRY_CANONICALIZATION_VERSION.endswith("/v1")


# --------------------------------------------------------------------------- #
# BR-2 surfaces are absent
# --------------------------------------------------------------------------- #
#: Types BR-1 must **not** define. Every one belongs to BR-2 under ADR §30/§32,
#: to another capability, or to a deferred decision.
FORBIDDEN_CLASS_NAMES = {
    # BR-2: the registry, the resolver and everything they need (§16.2, §17)
    "BenchmarkRegistry", "BenchmarkStore", "BenchmarkResolver",
    "BenchmarkResolution", "BenchmarkResolutionRequest",
    "BenchmarkResolutionResult", "BenchmarkLookup", "BenchmarkCatalog",
    "BenchmarkIndex", "BenchmarkRepository", "BenchmarkDirectory",
    "BenchmarkRegistrar", "BenchmarkRegistration", "BenchmarkRegistrationRecord",
    "BenchmarkAdmission", "BenchmarkAdmissionResult",
    "BenchmarkPublisher", "BenchmarkPublicationRecord", "SignedBenchmark",
    "SignedBenchmarkDefinition", "BenchmarkSignature", "BenchmarkSigner",
    "BenchmarkTrustAnchor", "BenchmarkKeyRing",
    "BenchmarkRevocation", "BenchmarkRevocationRecord",
    "BenchmarkSuccessorReference", "BenchmarkSupersessionRecord",
    "BenchmarkApprovalVerifier", "BenchmarkAuditRecord",
    # Governance Contracts owns these (§6.3, §14); DD-11 keeps one open.
    "BenchmarkReference", "AssessedSystemBinding", "SystemManifest",
    "SubjectContext",
    # Other capabilities' artifacts (§18, §7)
    "BenchmarkResult", "BenchmarkComparison", "BenchmarkComparisonResult",
    "MetricObservation", "ObservedMeasurement",
    "EvidenceVerificationReceipt", "SignedEvidenceVerificationReceipt",
    "EvidenceAdmissionPort", "PolicyDecision", "PolicyApplicabilityResolver",
    "ReadinessEvaluator", "ReadinessDetermination",
    "ValuationResult", "RoiDetermination", "AttributionAssessment",
    "ActionGate", "DeploymentAuthorizer", "ExecutionReceipt",
    "CertificateAuthority", "KmsClient",
}

#: The BR-1 surface ADR §30 assigns to this milestone. Each must exist.
REQUIRED_BR1_CLASS_NAMES = {
    "BenchmarkCoordinate",
    "BenchmarkScope",
    "BenchmarkApplicabilityCoordinate",
    "BenchmarkMeasurementSemantics",
    "BenchmarkEffectivePeriod",
    "BenchmarkSourceRequirements",
    "BenchmarkApprovalReference",
    "BenchmarkSupersessionDeclaration",
    "CanonicalBenchmarkDefinitionIdentity",
    "BenchmarkLifecycleState",
    "BenchmarkRefusalReason",
    "BenchmarkContractError",
}


@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_CLASS_NAMES))
def test_no_out_of_scope_type_is_defined(forbidden):
    assert forbidden not in _defined_class_names()
    assert forbidden not in api.__all__


@pytest.mark.parametrize("required", sorted(REQUIRED_BR1_CLASS_NAMES))
def test_the_ratified_br1_type_is_defined_and_exported(required):
    """The boundary cuts both ways: BR-1 must also *reach* its milestone."""

    assert required in _defined_class_names()
    assert required in api.__all__


def test_no_function_performs_a_br2_operation():
    banned = {
        "register", "register_benchmark", "resolve", "resolve_benchmark",
        "lookup", "get_benchmark", "find_benchmark", "latest", "current",
        "publish", "sign", "verify_signature", "revoke", "supersede",
        "admit", "store", "save", "load_benchmark", "list_benchmarks",
    }
    defined = _defined_function_names()
    assert not (defined & banned), sorted(defined & banned)


def test_no_module_performs_io_or_networking():
    """A registry needs storage and a network; a contract package needs neither."""

    banned_modules = {
        "socket", "http", "urllib", "sqlite3", "shutil", "subprocess",
        "asyncio", "ssl", "pickle", "shelve", "dbm", "tempfile", "os",
    }
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            assert not (roots & banned_modules), (
                path.name, sorted(roots & banned_modules)
            )


def test_no_module_performs_cryptography():
    """§16.2 stage 4 — publisher signature and key trust are BR-2's."""

    banned = {"hashlib", "hmac", "secrets", "cryptography", "nacl", "ecdsa"}
    users = {}
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            for root in roots & banned:
                users.setdefault(root, set()).add(path.name)
    # ``hashlib`` is the one exception and is used in exactly one module, for the
    # one digest path. A digest is not a signature (B-5, §13.3), and no other
    # cryptographic primitive appears anywhere.
    assert set(users) <= {"hashlib"}, {k: sorted(v) for k, v in users.items()}
    assert users.get("hashlib") == {"canonical.py"}, users


def test_no_placeholder_stub_or_permissive_marker():
    markers = ("TODO", "FIXME", "XXX", "NotImplementedError", "pragma: no cover",
               "allow_all", "AllowAll", "FakeRegistry", "NullRegistry",
               "StubResolver", "InMemoryRegistry", "PermissiveResolver")
    for path in _sources():
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            assert marker not in source, (path.name, marker)


def test_no_public_dataclass_carries_a_field_reserved_for_a_later_milestone():
    reserved_markers = ("reserved", "placeholder", "todo", "future", "_br2",
                        "unused", "tbd")
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                lowered = field.name.lower()
                for marker in reserved_markers:
                    assert marker not in lowered, (name, field.name)


def test_every_public_enum_member_is_reachable_and_meaningful():
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            members = list(obj)
            assert members, name
            values = [m.value for m in members]
            assert len(set(values)) == len(values), name
            assert all(v == v.upper() for v in values), name


# --------------------------------------------------------------------------- #
# Ownership: this package is not the things it must not be
# --------------------------------------------------------------------------- #
def test_the_distribution_and_namespace_are_the_ratified_ones():
    assert ugence_benchmark_registry.__name__ == "ugence_benchmark_registry"
    manifest = PKG_ROOT.parents[1] / "public_api.json"
    if manifest.is_file():
        import json

        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["distribution"] == "ugence-benchmark-registry"
        assert data["namespace"] == "ugence_benchmark_registry"


def test_no_uvi_scoped_alias_is_minted():
    """ADR §6.2 prohibits ``ugence-uvi-benchmark-registry`` by name (B-1)."""

    manifest = PKG_ROOT.parents[1] / "public_api.json"
    if manifest.is_file():
        import json

        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "uvi" not in data["distribution"]
        assert "uvi" not in data["namespace"]


def test_the_comparative_governance_benchmark_dataset_is_untouched():
    """ADR §6.3 — a different thing that shares the word "benchmark".

    The frozen ``comparative_governance_benchmark`` dataset gates
    ``platform_freeze.verify``'s ``benchmark_identity`` check. Nothing in this
    package imports it, names it in code, or carries any of its identifiers as a
    value.

    Checked over the AST rather than the raw text: the package docstring
    *mentions* the dataset in order to disclaim it, exactly as ADR §6.3 does, and
    disclaiming a collision is the opposite of creating one.
    """

    tokens = ("comparative_governance_benchmark",
              "dgm-comparative-governance-benchmark",
              "platform_freeze")
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstrings = {
            id(ast.get_docstring(node, clean=False))
            for node in ast.walk(tree)
            if isinstance(
                node,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            )
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(t in alias.name for t in tokens), path.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not any(t in node.module for t in tokens), path.name
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                assert not any(t in node.name for t in tokens), path.name
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node.value) in docstrings:
                    continue
                assert not any(t in node.value for t in tokens), (
                    path.name, node.value[:60]
                )


def test_no_readiness_forecasting_attribution_or_valuation_surface_exists():
    """§20, §21 — UVI-EV-1/M-3R.4 and GV-F..GV-V are DEFERRED and not started."""

    banned = ("readiness", "forecast", "attribution", "valuation", "roi",
              "monetary", "financial", "counterfactual", "gate", "indicator",
              "determination")
    for name in api.__all__:
        for token in banned:
            assert token not in name.lower(), name
    defined = _defined_class_names() | _defined_function_names()
    for name in defined:
        for token in banned:
            assert token not in name.lower(), name


def test_no_policy_authority_integration_surface_exists():
    """§19 — a policy citation is not a resolution, and BR-1 integrates nothing."""

    # ``BenchmarkSourceRequirements`` is ADR §15 row 16 — the *source and
    # provenance* requirements a definition states about its own data. It is not
    # a Policy Authority requirement, so "requirement" alone is not the banned
    # token; the policy-scoped spellings are.
    banned = ("policy", "entitlement", "policyrequirement", "citation")
    for name in api.__all__:
        for token in banned:
            assert token not in name.lower(), name


def test_no_cloud_scaling_or_deployment_surface_exists():
    banned = ("deploy", "scal", "capacity", "provision", "execute", "execution")
    for name in api.__all__:
        for token in banned:
            assert token not in name.lower(), name
