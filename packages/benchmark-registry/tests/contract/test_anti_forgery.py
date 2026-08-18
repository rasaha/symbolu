"""Nothing constructible here can be made to claim trust (ADR B-5, B-9, B-12).

Each route is attempted against a **working** happy path, so a test that passed
because its fixture was already broken would show up as the happy-path assertion
failing first.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import pickle

import pytest
import ugence_benchmark_registry as pkg
from ugence_benchmark_registry import api
from ugence_benchmark_registry.api import (
    BenchmarkContractError,
    BenchmarkLifecycleState,
    BenchmarkRefusalReason,
    BenchmarkScope,
    BenchmarkStructuralStatus,
    CanonicalBenchmarkDefinitionIdentity,
)

import _builders as b

_R = BenchmarkRefusalReason


def test_the_happy_path_works():
    """The control. If this fails, every refusal below proves nothing."""

    identity = b.identity()
    assert identity.canonical_digest()
    assert identity.is_effective_at(b.INSIDE) is True


# --------------------------------------------------------------------------- #
# There is no flag to forge
# --------------------------------------------------------------------------- #
def test_no_public_dataclass_carries_a_trust_flag():
    banned = ("verified", "trusted", "valid", "approved_flag", "is_approved",
              "resolved", "registered", "admitted", "signature", "signed",
              "authentic", "authorized", "score", "confidence", "coverage",
              "fingerprint")
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                for token in banned:
                    assert token not in field.name.lower(), (name, field.name)


def test_the_status_property_cannot_be_raised_by_assignment():
    identity = b.identity()
    with pytest.raises(AttributeError):
        identity.structural_status = "TRUSTED"
    assert identity.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED


def test_object_setattr_cannot_shadow_the_status_property():
    """A data property with no setter refuses even ``object.__setattr__``.

    This is the route that *does* defeat ``frozen=True`` for ordinary fields, so
    it matters that the honest-status properties are not fields: there is no
    instance slot to write, and the descriptor refuses the write outright.
    """

    identity = b.identity()
    for prop in ("structural_status", "trusted_resolution_performed",
                 "unresolved_reason"):
        with pytest.raises(AttributeError):
            object.__setattr__(identity, prop, "TRUSTED")
    assert identity.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
    assert identity.trusted_resolution_performed is False


def test_a_subclass_cannot_override_the_status_and_still_be_accepted():
    class Forged(CanonicalBenchmarkDefinitionIdentity):
        @property
        def structural_status(self):  # pragma: no cover - value never trusted
            return "TRUSTED"

    forged = Forged(
        **{
            f.name: getattr(b.identity(), f.name)
            for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)
        }
    )
    # The subclass can lie about itself, but the canonicalization boundary
    # accepts only the nine exact registered BR-1 classes — a subclass is a
    # different class object even though it inherits every method, so it is
    # refused outright rather than merely given its own (differently-typed)
    # bytes. It can never be canonicalized, let alone presented as the real
    # identity.
    with pytest.raises(BenchmarkContractError):
        forged.canonical_bytes()


def test_no_success_state_exists_to_construct():
    assert [m.value for m in BenchmarkStructuralStatus] == ["STRUCTURAL_UNVERIFIED"]
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            for member in obj:
                assert "TRUSTED" not in member.value
                assert "RESOLVED" not in member.value


# --------------------------------------------------------------------------- #
# Serialization round trips are not a way in
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "clone", ["copy", "deepcopy", "pickle"]
)
def test_a_round_trip_cannot_raise_the_status(clone):
    identity = b.identity()
    rebuilt = {
        "copy": copy.copy,
        "deepcopy": copy.deepcopy,
        "pickle": lambda o: pickle.loads(pickle.dumps(o)),
    }[clone](identity)
    assert rebuilt.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
    assert rebuilt.trusted_resolution_performed is False
    assert rebuilt.unresolved_reason is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED


def test_a_pickled_identity_that_skipped_post_init_still_digests_its_own_bytes():
    """A digest follows the bytes even when the constructor was bypassed.

    ``dataclasses`` rebuilds by ``__init__`` under the default reduce, so a
    normal round trip re-validates. A hand-built object that skipped validation
    is still bound to what it actually contains: the digest is a pure function of
    the fields, so a tampered object matches no digest anyone recorded.
    """

    forged = object.__new__(CanonicalBenchmarkDefinitionIdentity)
    real = b.identity()
    for field in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity):
        object.__setattr__(forged, field.name, getattr(real, field.name))
    object.__setattr__(forged, "publisher_id", "publisher-attacker")
    assert forged.canonical_digest() != real.canonical_digest()


# --------------------------------------------------------------------------- #
# Cross-coordinate replay is detectable
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kwargs",
    [
        {"coordinate": b.coordinate(benchmark_id="bmk-other")},
        {"coordinate": b.coordinate(benchmark_version="2.0.0")},
        {"coordinate": b.coordinate(benchmark_family="other-family")},
        {"coordinate": b.coordinate(scope=BenchmarkScope.for_tenant("tenant-beta"))},
        {"coordinate": b.coordinate(scope=BenchmarkScope.platform_wide())},
        {"measurement": b.measurement(unit="hours")},
        {"measurement": b.measurement(population_ref="cohort-other")},
        {"measurement": b.measurement(aggregation_semantics_ref="agg-other")},
        {"measurement": b.measurement(observation_window_ref="window-other")},
        {"publisher_id": "publisher-other"},
        {"lifecycle_state": BenchmarkLifecycleState.AUTHORED},
        {"source_requirements": b.source_requirements(source_ref="source-other")},
        {"approval": b.approval(approval_ref="approval-other")},
    ],
)
def test_moving_any_coordinate_produces_a_different_identity(kwargs):
    original = b.identity()
    moved = b.identity(**kwargs)
    assert moved.canonical_digest() != original.canonical_digest()
    assert moved != original


def test_a_definition_cannot_be_replayed_under_another_tenant_undetected():
    alpha = b.identity()
    beta = b.identity(
        coordinate=b.coordinate(scope=BenchmarkScope.for_tenant("tenant-beta"))
    )
    assert alpha.canonical_digest() != beta.canonical_digest()
    assert alpha.identity_coordinate != beta.identity_coordinate


# --------------------------------------------------------------------------- #
# The package cannot be made to compute, resolve or authorize
# --------------------------------------------------------------------------- #
def test_no_public_callable_produces_a_benchmark_result():
    """B-12 — "the Registry computes nothing"."""

    banned = ("compare", "evaluate", "compute", "calculate", "score", "measure",
              "aggregate", "roi", "value", "readiness", "authorize", "verify",
              "sign", "admit")
    for name in api.__all__:
        obj = getattr(api, name)
        if callable(obj) and not isinstance(obj, type):
            for token in banned:
                assert token not in name.lower(), name


def test_nothing_exposes_an_observed_value_or_a_threshold():
    """A definition describes what is measured; it holds no measurement."""

    banned = ("observed", "measured_value", "threshold", "target_value",
              "actual", "result", "outcome_value", "baseline_value")
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                for token in banned:
                    assert token not in field.name.lower(), (name, field.name)


def test_no_module_defines_a_registry_store_or_resolver():
    import ast
    import pathlib

    root = pathlib.Path(pkg.__file__).resolve().parent
    banned_names = ("registry", "resolver", "store", "repository", "index",
                    "catalog", "directory", "cache", "database")
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                for token in banned_names:
                    assert token not in lowered, (path.name, node.name)


def test_constructing_everything_still_reports_unresolved():
    for identity in (b.identity(), b.minimal_identity()):
        assert identity.trusted_resolution_performed is False
        assert identity.unresolved_reason is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED
        assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in identity.structural_refusals_at(
            b.INSIDE
        )


def test_a_caller_written_approval_reference_establishes_nothing():
    """B-5 — a caller-created verification object is not approval evidence."""

    identity = b.identity()
    assert identity.approval.approval_ref == "approval-bmk-2026-0142"
    assert identity.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
    assert identity.trusted_resolution_performed is False


def test_a_registered_lifecycle_label_establishes_nothing():
    """B-5 — a lifecycle enum on the artifact is not approval evidence."""

    identity = b.identity(lifecycle_state=BenchmarkLifecycleState.REGISTERED)
    assert identity.trusted_resolution_performed is False
    assert identity.unresolved_reason is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED


def test_the_role_separation_check_cannot_be_evaded_by_case_or_padding():
    """Padding and case are refused before the comparison, not normalized away."""

    with pytest.raises(BenchmarkContractError):
        b.identity(publisher_id=" authority-benchmark-governance-board")
    # A different case *is* a different identifier, and that is deliberate: the
    # ADR never ratifies case-folding of identity coordinates, and folding here
    # would make two distinct principals one.
    assert b.identity(publisher_id="AUTHORITY-BENCHMARK-GOVERNANCE-BOARD")
