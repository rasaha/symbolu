"""D-10 — supersession is out of scope and every path fails closed."""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import _builders as fx
from ugence_benchmark_registry import BenchmarkSupersessionStatus
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryRefusalReason,
    fault_class_for,
)

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"


def test_happy_the_typed_unsupported_outcome_exists():
    assert BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION.value == (
        "UNSUPPORTED_SUPERSESSION"
    )


def test_it_is_classified_as_a_lifecycle_integrity_fault():
    assert (
        fault_class_for(BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION)
        is BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY
    )
    assert BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES[
        BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION
    ] is BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY


def test_no_supersession_field_exists_on_any_br2_contract():
    banned = ("supersede", "superseded", "successor", "predecessor_version")
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        for f in dataclasses.fields(builder()):
            for token in banned:
                assert token not in f.name.lower(), f.name


def test_no_supersession_api_is_exported():
    import ugence_benchmark_registry_authority as pkg

    for symbol in pkg.__all__:
        lowered = symbol.lower()
        if "supersession" in lowered:
            assert symbol == "BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS" or (
                "UNSUPPORTED" in symbol
            ), symbol
        assert "successor" not in lowered, symbol


def test_no_function_anywhere_implements_or_infers_supersession():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                lowered = node.name.lower()
                for token in ("supersede", "successor", "newer", "supersession"):
                    if token in lowered:
                        offenders.append(f"{path.name}: {node.name}")
    assert offenders == [], offenders


def test_no_version_ordering_or_comparison_exists_anywhere():
    """D-10: BR-2 must not infer authority from SemVer ordering."""

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                lowered = node.name.lower()
                for token in ("compare_version", "version_order", "is_newer",
                              "latest_of", "max_version", "sort_versions"):
                    if token in lowered:
                        offenders.append(f"{path.name}: {node.name}")
    assert offenders == [], offenders


def test_the_package_never_parses_or_compares_a_semantic_version():
    """It requires a BR-1 coordinate, which already validated the version once."""

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text()
        for marker in ("SEMVER", "semver", "MAJOR.MINOR"):
            for line in text.splitlines():
                stripped = line.strip()
                if marker in stripped and not stripped.startswith(("#", "*")):
                    if '"""' in stripped or stripped.startswith(("*", "-")):
                        continue
                    if "=" in stripped and "re.compile" in stripped:
                        offenders.append(f"{path.name}: {stripped[:60]}")
    assert offenders == [], offenders


def test_br1_still_records_supersession_as_undetermined_only():
    """The frozen layer's posture is unchanged and BR-2 adds nothing to it."""

    assert [s.value for s in BenchmarkSupersessionStatus] == ["UNDETERMINED"]


def test_no_br2_contract_carries_a_supersession_declaration():
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        contract = builder()
        assert not hasattr(contract, "supersession")
        assert not hasattr(contract, "superseded_by")


def test_a_supersession_transition_is_not_in_the_closed_relation():
    from ugence_benchmark_registry_authority.api import (
        BENCHMARK_REGISTRATION_TRANSITIONS,
        BenchmarkRegistrationState,
    )

    names = {s.name for s in BenchmarkRegistrationState}
    assert "SUPERSEDED" not in names
    for successors in BENCHMARK_REGISTRATION_TRANSITIONS.values():
        for successor in successors:
            assert successor.name != "SUPERSEDED"


def test_the_refusal_is_the_only_supersession_surface_in_the_package():
    import ugence_benchmark_registry_authority as pkg

    supersession_symbols = [
        s for s in dir(pkg) if "supersession" in s.lower() and not s.startswith("_")
    ]
    assert supersession_symbols == []
    assert (
        BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION
        in set(BenchmarkRegistryRefusalReason)
    )
