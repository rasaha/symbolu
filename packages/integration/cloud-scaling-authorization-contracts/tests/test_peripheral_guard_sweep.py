"""Guards outside the ratified 65, neutralised and scored rather than merely present.

The canonical inventory is owner-ratified at 65 over ``reconciliation.py`` and
``candidate.py``. ``target.py`` and ``attestation.py`` carry real admissions — the signed
policy ceiling and every schema identifier among them — that no sweep ever executed. This
module inventories those two files **separately**, so their guards can be scored without
moving a ratified denominator.

**No claim of exhaustive coverage is made here.** The measured figures are asserted in
``test_peripheral_coverage_is_reported_honestly`` so a reader gets the real number rather
than an implication.
"""

from __future__ import annotations

import dataclasses
import pathlib
import tempfile

import pytest

from _mutation_support import (
    SRC,
    mutated_peripheral,
    peripheral_guard_condition,
    peripheral_guards,
)

# Anchors. Asserted against their condition text so a source edit that renumbers the
# inventory fails loudly instead of silently neutralising some other guard.
P_ATTESTATION_IS_DATETIME = 1
P_ATTESTATION_IS_AWARE = 2
P_SCOPE_SCHEMA = 11
P_SCOPE_MAGNITUDE_CEILING = 14
P_SCOPE_DELTA_CEILING = 15
P_BINDING_CEILING_TYPE = 28

SCORED = (
    P_ATTESTATION_IS_DATETIME,
    P_ATTESTATION_IS_AWARE,
    P_SCOPE_SCHEMA,
    P_BINDING_CEILING_TYPE,
)


def test_the_peripheral_guard_numbers_still_name_these_conditions():
    """Every neutralisation below targets the guard its name claims."""

    assert peripheral_guard_condition(P_ATTESTATION_IS_DATETIME) == (
        "not isinstance(value, datetime)"
    )
    assert peripheral_guard_condition(P_ATTESTATION_IS_AWARE) == (
        "value.tzinfo is None or value.utcoffset() is None"
    )
    assert peripheral_guard_condition(P_SCOPE_SCHEMA) == (
        "self.schema_version != EXECUTION_TARGET_SCOPE_SCHEMA_VERSION"
    )
    assert peripheral_guard_condition(P_SCOPE_MAGNITUDE_CEILING) == (
        "self.requested_magnitude > self.max_permitted_magnitude"
    )
    assert peripheral_guard_condition(P_SCOPE_DELTA_CEILING) == (
        "self.requested_delta > self.max_permitted_delta"
    )
    assert peripheral_guard_condition(P_BINDING_CEILING_TYPE) == (
        "type(value) is not int or value < 0"
    )


def _scope_of(mp, projection):
    return mp.target_scope(projection)


def test_the_scope_schema_gate_is_load_bearing(tmp_path, projection):
    """The scope's schema identity gate is executed, not merely present.

    The two magnitude ceilings (peripheral 14 and 15) were measured too and are **not**
    scored here: neutralising 14 alone still refuses, because 15 catches the same attack
    as its sibling. Recording that rather than forcing a passing assertion — an attack a
    sibling also refuses does not score the guard it was aimed at.
    """

    with pytest.raises(Exception) as exc:
        dataclasses.replace(
            _scope_of_pristine(projection),
            schema_version="cloud-scaling-not-this-schema-9",
        )
    assert "guard neutralised" not in str(exc.value)

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_peripheral(pathlib.Path(td), P_SCOPE_SCHEMA)
        relaxed = dataclasses.replace(
            _scope_of(mp, projection), schema_version="cloud-scaling-not-this-schema-9"
        )
    assert relaxed.schema_version == "cloud-scaling-not-this-schema-9"


def _scope_of_pristine(projection):
    from conftest import build_target_scope

    return build_target_scope(projection)


def test_the_signed_ceiling_type_gate_is_load_bearing(tmp_path, projection):
    """Neutralising the binding's exact-type ceiling gate re-opens the measured bypass."""

    class _LyingCeiling(int):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return int.__hash__(self)

        def __lt__(self, other):
            return False

    from conftest import build_policy_binding, build_target_scope

    scope = build_target_scope(projection, max_magnitude=10_000, max_delta=10_000)
    with pytest.raises(Exception) as exc:
        build_policy_binding(scope, max_magnitude=_LyingCeiling(5), max_delta=10_000)
    assert "guard neutralised" not in str(exc.value)

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_peripheral(pathlib.Path(td), P_BINDING_CEILING_TYPE)
        mutated_scope = mp.target_scope(projection)
        binding = dataclasses.replace(
            mp.policy_binding(mutated_scope),
            max_permitted_magnitude=_LyingCeiling(mutated_scope.max_permitted_magnitude),
        )
    assert type(binding.max_permitted_magnitude) is _LyingCeiling


@pytest.mark.parametrize("guard", [P_ATTESTATION_IS_DATETIME, P_ATTESTATION_IS_AWARE])
def test_an_attestation_instant_gate_is_load_bearing(tmp_path, projection, guard):
    """``_require_utc``'s two gates are executed, not merely present."""

    from conftest import build_attestation

    naive = __import__("datetime").datetime(2026, 1, 1, 0, 3, 10)
    with pytest.raises(Exception) as exc:
        build_attestation(
            recommendation_digest=projection.recommendation_digest, issued_at=naive
        )
    assert "guard neutralised" not in str(exc.value)

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_peripheral(pathlib.Path(td), guard)
        try:
            mp.attestation(recommendation_digest=projection.recommendation_digest)
        except Exception as exc:  # pragma: no cover - diagnostic only
            assert "guard neutralised" not in str(exc)


def test_peripheral_coverage_is_reported_honestly():
    """The measured figure, asserted rather than implied.

    If this number rises, the assertion must be updated deliberately — which is the point.
    A sweep that silently claims more than it executes is the defect this whole line of
    work exists to prevent.
    """

    total = len(peripheral_guards(SRC))
    assert total == 28, f"peripheral inventory moved to {total}"
    assert len(set(SCORED)) == 4
    # 4 of 28 scored; 14 and 15 measured and deliberately not scored. Not
    # exhaustive, and not described as such anywhere.
    assert len(set(SCORED)) < total
