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
import datetime
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
    P_SCOPE_MAGNITUDE_CEILING,
    P_BINDING_CEILING_TYPE,
)
"""Guards this module actually neutralises and observes. Nothing else is claimed.

``P_SCOPE_DELTA_CEILING`` is **not** here: with the magnitude ceiling widened far enough
for a delta-only attack, the request that clears it also clears the delta bound, so no
attack was found that guard 15 alone refuses. Recorded as unscored rather than asserted
into the list.
"""


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


def test_the_scope_magnitude_ceiling_is_load_bearing(tmp_path, projection):
    """Scored by widening the delta ceiling so its sibling cannot supply the refusal.

    With both ceilings at their fixture values the attack is caught by guard 15, which is
    why an earlier revision of this module left guard 14 unscored. Widening ``max_delta``
    isolates it.
    """

    from conftest import build_target_scope

    with pytest.raises(Exception) as exc:
        build_target_scope(projection, max_magnitude=5, max_delta=10_000)
    assert "guard neutralised" not in str(exc.value)
    assert "exceeds the permitted maximum" in str(exc.value)
    assert "delta" not in str(exc.value), "the delta sibling produced this refusal"

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_peripheral(pathlib.Path(td), P_SCOPE_MAGNITUDE_CEILING)
        scope = mp.target_scope(projection, max_magnitude=5, max_delta=10_000)
    assert scope.requested_magnitude > scope.max_permitted_magnitude


def test_the_scope_schema_gate_is_load_bearing(tmp_path, projection):
    """The scope's schema identity gate is executed, not merely present.

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


@pytest.mark.parametrize(
    "guard, bad_issued_at",
    [
        (P_ATTESTATION_IS_DATETIME, "2026-01-01T00:03:10.000000Z"),
        (P_ATTESTATION_IS_AWARE, datetime.datetime(2026, 1, 1, 0, 3, 10)),
    ],
)
def test_an_attestation_instant_gate_admits_exactly_when_it_is_removed(
    tmp_path, projection, guard, bad_issued_at
):
    """``_require_utc``'s two gates are executed, not merely present.

    The earlier form of this test was **vacuous**: ``MutatedPackage.attestation`` took no
    ``issued_at``, so its mutated half built the same honest attestation for every guard
    number and passed whatever was neutralised. The override added for this test is what
    makes the neutralisation observable at all.
    """

    from conftest import build_attestation

    with pytest.raises(Exception) as exc:
        build_attestation(
            recommendation_digest=projection.recommendation_digest,
            issued_at=bad_issued_at,
        )
    assert "guard neutralised" not in str(exc.value)

    pristine_message = str(exc.value)

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_peripheral(pathlib.Path(td), guard)
        try:
            evidence = mp.attestation(
                recommendation_digest=projection.recommendation_digest,
                issued_at=bad_issued_at,
            )
        except Exception as mutated:  # noqa: BLE001 - the shape of the failure is the point
            # Removing the type gate does not admit the value; it lets a non-datetime
            # reach the awareness gate, which crashes on `.tzinfo`. That is still a score:
            # the typed refusal this guard owns is gone, and no sibling supplies it.
            assert "guard neutralised" not in str(mutated)
            assert str(mutated) != pristine_message
            assert not isinstance(mutated, type(exc.value)), (
                "a sibling guard produced the same typed refusal"
            )
        else:
            assert evidence.issued_at == bad_issued_at


def test_peripheral_coverage_is_reported_honestly():
    """The measured figure, asserted rather than implied.

    If this number rises, the assertion must be updated deliberately — which is the point.
    A sweep that silently claims more than it executes is the defect this whole line of
    work exists to prevent.
    """

    total = len(peripheral_guards(SRC))
    assert total == 28, f"peripheral inventory moved to {total}"
    assert len(set(SCORED)) == 5
    # 5 of 28 scored. Guard 15 measured and deliberately not scored — see SCORED's note.
    # Not exhaustive, and not described as such anywhere.
    assert len(set(SCORED)) < total
