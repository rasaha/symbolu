"""The documented public API agrees with the actual package surface.

Rebuilds the public-API description from the imported
``ugence_benchmark_registry.api`` module and asserts it equals the committed
``public_api.json``. Catches an accidental export addition or removal, an
enum-value drift, a dataclass-field change, a field **reordering**, or a changed
pinned constant that the machine-readable snapshot does not reflect.

The same builder is used by the distribution verifier against the *installed*
wheel, so the source tree, the manifest, the wheel and an isolated installed
runtime are all held to one description.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_benchmark_registry as pkg
from ugence_benchmark_registry import api

_PKG_ROOT = pathlib.Path(pkg.__file__).resolve().parent
# tests/packaging/ -> tests/ -> packages/benchmark-registry/
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PUBLIC_API_JSON = _DIST_ROOT / "public_api.json"


def _kind(obj) -> str:
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return "enum"
        if issubclass(obj, Exception):
            return "exception"
        if dataclasses.is_dataclass(obj):
            return "dataclass"
        return "class"
    if callable(obj):
        return "function"
    return "constant"


def _constant_value(obj):
    """A JSON-representable, order-preserving rendering of a pinned constant.

    Recursive, so a nested collection is rendered structurally rather than
    through ``repr``. A ``repr`` would make the snapshot depend on Python's
    formatting rather than on the value.
    """

    if isinstance(obj, str):
        return obj
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (tuple, list)):
        return [_constant_value(v) for v in obj]
    if isinstance(obj, frozenset):
        return sorted(_constant_value(v) for v in obj)
    if hasattr(obj, "items"):  # the lifecycle transition mapping
        return {
            _constant_value(k): sorted(_constant_value(v) for v in value)
            for k, value in obj.items()
        }
    if isinstance(obj, (int, bool)) or obj is None:
        return obj
    raise AssertionError(f"unrenderable constant: {obj!r}")


def actual_surface(module=api, version=None) -> dict:
    symbols: dict = {}
    for name in sorted(module.__all__):
        if name == "__version__":
            continue
        obj = getattr(module, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            entry["values"] = [m.value for m in obj]
        elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        elif entry["kind"] == "constant":
            entry["value"] = _constant_value(obj)
        symbols[name] = entry
    return {
        "distribution": "ugence-benchmark-registry",
        "namespace": "ugence_benchmark_registry",
        "package_version": version or pkg.__version__,
        "curated_api_module": "ugence_benchmark_registry.api",
        "symbols": symbols,
    }


def test_documented_public_api_matches_actual():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    documented.pop("note", None)
    actual = actual_surface()
    for key in ("distribution", "namespace", "package_version", "curated_api_module"):
        assert documented[key] == actual[key], key
    assert documented["symbols"] == actual["symbols"]


def test_curated_api_names_match_module_all():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    expected = {n for n in api.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_top_level_reexports_match_the_curated_api():
    """The package root and ``api`` export the same names (plus ``api`` itself)."""

    assert set(pkg.__all__) - {"api"} == set(api.__all__)
    for name in api.__all__:
        if name == "__version__":
            continue
        assert getattr(pkg, name) is getattr(api, name), name


def test_all_is_explicit_and_free_of_duplicates():
    for module in (pkg, api):
        assert isinstance(module.__all__, list)
        assert len(set(module.__all__)) == len(module.__all__)


def test_no_private_name_is_exported():
    for name in api.__all__:
        assert name == "__version__" or not name.startswith("_"), name


def test_py_typed_marker_present():
    assert (_PKG_ROOT / "py.typed").is_file(), "PEP 561 py.typed marker missing"


def test_the_manifest_records_the_package_version():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    assert documented["package_version"] == pkg.__version__ == "0.1.0"


def test_the_version_module_is_the_single_source():
    from ugence_benchmark_registry import version

    assert version.__version__ == pkg.__version__ == api.__version__ == "0.1.0"


#: The 32 curated symbols BR-1 ships. Pinned by name so a removal is caught even
#: if the manifest were regenerated wholesale.
BR1_CURATED_SYMBOLS = [
    "BenchmarkContractError",
    "BenchmarkCanonicalizationError",
    "BenchmarkLifecycleError",
    "BenchmarkApplicabilityDeclaration",
    "BenchmarkScopeKind",
    "TemporalBoundDeclaration",
    "BenchmarkLifecycleState",
    "BenchmarkStructuralStatus",
    "BenchmarkSupersessionStatus",
    "BenchmarkRefusalReason",
    "BenchmarkApplicabilityCoordinate",
    "BenchmarkScope",
    "BenchmarkCoordinate",
    "BenchmarkMeasurementSemantics",
    "BenchmarkEffectivePeriod",
    "BenchmarkSourceRequirements",
    "BenchmarkApprovalReference",
    "BenchmarkSupersessionDeclaration",
    "CanonicalBenchmarkDefinitionIdentity",
    "canonical_bytes",
    "canonical_digest",
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION",
    "BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN",
    "BENCHMARK_IDENTITY_COORDINATES",
    "BENCHMARK_LIFECYCLE_ORDER",
    "BENCHMARK_LIFECYCLE_TRANSITIONS",
    "BENCHMARK_TERMINAL_LIFECYCLE_STATES",
    "BENCHMARK_REFUSAL_REASONS",
    "BR1_BENCHMARK_REFUSAL_REASONS",
]


def test_all_br1_symbols_are_exported():
    exported = set(api.__all__)
    missing = [n for n in BR1_CURATED_SYMBOLS if n not in exported]
    assert missing == [], missing
    for name in BR1_CURATED_SYMBOLS:
        assert getattr(pkg, name) is getattr(api, name), name


def test_the_curated_surface_size_is_pinned():
    """A symbol added or removed without updating the manifest fails here."""

    exported = [n for n in api.__all__ if n != "__version__"]
    assert len(exported) == 31
    assert set(exported) == set(BR1_CURATED_SYMBOLS)


def test_pinned_constants_are_snapshotted_with_their_values():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    constants = {
        name: entry
        for name, entry in documented["symbols"].items()
        if entry["kind"] == "constant"
    }
    assert set(constants) == {
        "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION",
        "BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN",
        "BENCHMARK_IDENTITY_COORDINATES",
        "BENCHMARK_LIFECYCLE_ORDER",
        "BENCHMARK_LIFECYCLE_TRANSITIONS",
        "BENCHMARK_TERMINAL_LIFECYCLE_STATES",
        "BENCHMARK_REFUSAL_REASONS",
        "BR1_BENCHMARK_REFUSAL_REASONS",
    }
    for entry in constants.values():
        assert "value" in entry


def test_the_single_digest_domain_is_snapshotted_and_pinned():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    domain = documented["symbols"]["BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN"][
        "value"
    ]
    assert domain == api.BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN
    assert domain == "ugence.benchmark-registry/benchmark-definition-identity/v1"
    version = documented["symbols"]["BENCHMARK_REGISTRY_CANONICALIZATION_VERSION"][
        "value"
    ]
    assert version == "ugence.benchmark-registry/canonicalization/v1"
    assert domain != version


def test_exactly_one_digest_domain_is_minted():
    """DD-9 — mint a tag only for an artifact that exists (ADR §22.1)."""

    domains = [
        name
        for name in api.__all__
        if name.endswith("_DIGEST_DOMAIN")
    ]
    assert domains == ["BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN"]


def test_no_br2_domain_is_reserved():
    for name in api.__all__:
        upper = name.upper()
        for banned in ("REGISTRATION", "RESOLUTION_RESULT", "SIGNED", "SIGNATURE",
                       "TRUST_ANCHOR", "REVOCATION", "PUBLICATION", "AUDIT",
                       "SUCCESSOR"):
            assert banned not in upper, name


def test_enum_member_order_is_snapshotted_not_just_the_member_set():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    values = documented["symbols"]["BenchmarkRefusalReason"]["values"]
    assert values == [m.value for m in api.BenchmarkRefusalReason]
    assert values[0] == "BENCHMARK_DEFINITION_MISSING"
    assert values[-1] == "BENCHMARK_RESOLUTION_NOT_PERFORMED"
    assert len(values) == 17


def test_every_dataclass_keeps_its_exact_field_order():
    """A reordered field changes canonical bytes and therefore every digest."""

    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    expected = {
        "BenchmarkApplicabilityCoordinate": ["declaration", "value"],
        "BenchmarkScope": ["kind", "tenant_id"],
        "BenchmarkCoordinate": [
            "benchmark_id", "benchmark_family", "benchmark_version", "scope",
            "geography", "domain",
        ],
        "BenchmarkMeasurementSemantics": [
            "intended_outcome_ref", "metric_ref", "unit",
            "measurement_protocol_ref", "population_ref",
            "aggregation_semantics_ref", "observation_window_ref",
        ],
        "BenchmarkEffectivePeriod": [
            "effective_from", "end_declaration", "effective_to",
        ],
        "BenchmarkSourceRequirements": [
            "source_ref", "provenance_requirement_refs",
        ],
        "BenchmarkApprovalReference": [
            "approval_ref", "approval_authority_ref", "approved_content_digest",
        ],
        "BenchmarkSupersessionDeclaration": ["status"],
        "CanonicalBenchmarkDefinitionIdentity": [
            "coordinate", "content_digest", "measurement", "effective_period",
            "source_requirements", "approval", "publisher_id",
            "lifecycle_state", "supersession",
        ],
    }
    for name, fields in expected.items():
        assert documented["symbols"][name]["fields"] == fields, name
        assert [
            f.name for f in dataclasses.fields(getattr(api, name))
        ] == fields, name


def test_every_enum_keeps_its_exact_member_order():
    expected = {
        "BenchmarkApplicabilityDeclaration": ["APPLICABLE", "NOT_APPLICABLE"],
        "BenchmarkScopeKind": ["PLATFORM_WIDE", "TENANT"],
        "TemporalBoundDeclaration": ["BOUNDED", "OPEN_ENDED"],
        "BenchmarkLifecycleState": [
            "AUTHORED", "APPROVED", "REGISTERED", "REVOKED",
        ],
        "BenchmarkStructuralStatus": ["STRUCTURAL_UNVERIFIED"],
        "BenchmarkSupersessionStatus": ["UNDETERMINED"],
    }
    for name, members in expected.items():
        assert [m.value for m in getattr(api, name)] == members, name


def test_the_twenty_adr_15_coordinates_are_snapshotted_in_order():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    coordinates = documented["symbols"]["BENCHMARK_IDENTITY_COORDINATES"]["value"]
    assert coordinates == list(api.BENCHMARK_IDENTITY_COORDINATES)
    assert len(coordinates) == 20
    assert coordinates[0] == "coordinate.benchmark_id"
    assert coordinates[-1] == "supersession"
