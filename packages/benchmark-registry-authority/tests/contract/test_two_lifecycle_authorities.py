"""Two lifecycle authorities, never merged, with no automatic bridge either way."""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

import _builders as fx
from ugence_benchmark_registry import BenchmarkLifecycleState
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_BANNED_REGISTRATION_STATE_NAMES,
    BenchmarkRegistrationState,
)

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"


def test_happy_the_two_vocabularies_are_different_types():
    assert BenchmarkRegistrationState is not BenchmarkLifecycleState


def test_the_two_vocabularies_have_different_membership():
    assert {s.value for s in BenchmarkLifecycleState} == {
        "AUTHORED",
        "APPROVED",
        "REGISTERED",
        "REVOKED",
    }
    assert {s.value for s in BenchmarkRegistrationState} == {
        "SUBMITTED",
        "ADMITTED",
        "REGISTERED",
        "REVOKED",
        "REJECTED",
    }


def test_the_shared_spellings_compare_equal_as_strings_and_that_is_the_hazard():
    """``REGISTERED`` and ``REVOKED`` exist in both, and **compare equal**.

    Both vocabularies are ``str``-valued enums, so
    ``BenchmarkLifecycleState.REGISTERED == BenchmarkRegistrationState.REGISTERED``
    is :data:`True` and the two hash alike. That is not a defect to be asserted
    away — it is the precise hazard D-08 exists to contain, and asserting the
    opposite would be asserting something false.

    What closes it is that they are **different objects of different types**, and
    that every boundary in this package uses ``type(x) is Expected`` rather than
    equality. The next two tests prove both halves.
    """

    assert BenchmarkLifecycleState.REGISTERED == BenchmarkRegistrationState.REGISTERED
    assert set(BenchmarkLifecycleState) & set(BenchmarkRegistrationState)


def test_the_shared_spellings_are_different_objects_of_different_types():
    assert (
        BenchmarkLifecycleState.REGISTERED
        is not BenchmarkRegistrationState.REGISTERED
    )
    assert (
        BenchmarkLifecycleState.REVOKED is not BenchmarkRegistrationState.REVOKED
    )
    assert type(BenchmarkLifecycleState.REGISTERED) is not type(
        BenchmarkRegistrationState.REGISTERED
    )


def test_equality_never_gets_a_br1_state_past_a_br2_boundary():
    """Exact-type checks, not equality, are what keep the vocabularies apart."""

    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryContractError,
    )

    for br1_state in BenchmarkLifecycleState:
        with pytest.raises(BenchmarkRegistryContractError):
            fx.resolution_record(declared_registration_state=br1_state)


def test_a_br1_state_cannot_be_used_where_a_br2_state_is_required():
    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryContractError,
    )

    with pytest.raises(BenchmarkRegistryContractError):
        fx.resolution_record(
            declared_registration_state=BenchmarkLifecycleState.REGISTERED
        )


def test_no_conversion_helper_bridges_the_two_in_either_direction():
    """Asserted as an **absence**: no function anywhere maps one to the other."""

    import ugence_benchmark_registry_authority as pkg

    banned_names = (
        "to_registration_state",
        "from_lifecycle_state",
        "as_registration_state",
        "lifecycle_to_registration",
        "registration_to_lifecycle",
        "convert_lifecycle",
        "bridge_lifecycle",
    )
    for name in banned_names:
        assert not hasattr(pkg, name), name
        assert name not in pkg.__all__

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                lowered = node.name.lower()
                if "lifecycle" in lowered and "registration" in lowered:
                    offenders.append(f"{path.name}: {node.name}")
    assert offenders == [], offenders


def test_no_code_path_reads_a_br1_lifecycle_state_at_all():
    """BR-1's embedded state is never consulted, so it can establish nothing."""

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "lifecycle_state":
                offenders.append(path.name)
            if isinstance(node, ast.Name) and node.id == "BenchmarkLifecycleState":
                offenders.append(f"{path.name}: BenchmarkLifecycleState")
    assert offenders == [], offenders


def test_no_field_named_lifecycle_state_exists_on_any_br2_contract():
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        for f in dataclasses.fields(builder()):
            assert f.name != "lifecycle_state"


def test_no_br2_field_name_collides_with_a_br1_lifecycle_field_name():
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        for f in dataclasses.fields(builder()):
            assert not f.name.startswith("lifecycle")


def test_a_declared_br2_state_establishes_nothing():
    """A payload saying REGISTERED was appended by nobody at BR-2A."""

    event = fx.registration_event()
    assert event.declared_state is BenchmarkRegistrationState.REGISTERED
    assert event.registry_admission_established is False
    assert event.trusted_resolution_established is False


# --------------------------------------------------------------------------- #
# The name ban
# --------------------------------------------------------------------------- #
def test_no_banned_state_name_appears_in_any_enum_member():
    for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
        assert banned not in {s.name for s in BenchmarkRegistrationState}
        assert banned not in {s.value for s in BenchmarkRegistrationState}


def test_no_banned_name_appears_in_any_exported_symbol():
    import ugence_benchmark_registry_authority as pkg

    for symbol in pkg.__all__:
        upper = symbol.upper()
        for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
            assert banned not in upper, f"{symbol} carries the banned name {banned}"


def test_no_banned_name_appears_in_any_enum_member_in_the_package():
    """The ban is on **state names**, so it is checked where states are named.

    Every enum member across the package, every class name, and every exported
    symbol. It is deliberately *not* a substring scan over all identifiers: the
    permanently-``False`` property ``active_eligibility_established`` legitimately
    contains "active" while asserting the exact opposite of an ``ACTIVE`` state,
    and banning it would be banning the disclaimer rather than the claim.
    """

    import enum

    import ugence_benchmark_registry_authority as pkg

    offenders = []
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol, None)
        if isinstance(value, enum.EnumMeta):
            for member in value:
                for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
                    if banned in member.name.upper() or banned in str(
                        member.value
                    ).upper():
                        offenders.append(f"{symbol}.{member.name} ({banned})")
    assert offenders == [], offenders


def test_no_banned_name_appears_in_any_class_name_in_the_package():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                upper = node.name.upper()
                for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
                    if banned in upper:
                        offenders.append(f"{path.name}: {node.name} ({banned})")
    assert offenders == [], offenders


def test_no_banned_name_appears_in_any_declared_state_field_value():
    """The states a payload can actually declare are the ratified five."""

    declared = set()
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        contract = builder()
        state = getattr(contract, "declared_state", None)
        if state is not None:
            declared.add(state.value)
        state = getattr(contract, "declared_registration_state", None)
        if state is not None:
            declared.add(state.value)
    assert declared <= {s.value for s in BenchmarkRegistrationState}
    for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
        assert banned not in declared


def test_the_ban_list_is_exactly_the_six_ratified_names():
    assert BENCHMARK_BANNED_REGISTRATION_STATE_NAMES == frozenset(
        {"ACTIVE", "PUBLISHED", "CURRENT", "DEFAULT", "SUSPENDED", "DEPRECATED"}
    )


def test_no_reversible_sounding_state_exists():
    names = {s.name for s in BenchmarkRegistrationState}
    for reversible in ("PAUSED", "HELD", "DISABLED", "INACTIVE", "PENDING"):
        assert reversible not in names
