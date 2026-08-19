"""Half-open effective periods, exact boundaries, no clock (ADR §17.9, §22).

§17.9: "Half-open effective periods — ``[start, end)``; boundary semantics
stated once and applied identically everywhere."
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from ugence_benchmark_registry.api import (
    BenchmarkContractError,
    BenchmarkEffectivePeriod,
    BenchmarkRefusalReason,
)

import _builders as b

_R = BenchmarkRefusalReason

MICRO = timedelta(microseconds=1)


def _bounded():
    return BenchmarkEffectivePeriod.bounded(b.EFFECTIVE_FROM, b.EFFECTIVE_TO)


# --------------------------------------------------------------------------- #
# The three boundary instants
# --------------------------------------------------------------------------- #
def test_the_start_bound_is_inclusive():
    period = _bounded()
    assert period.is_effective_at(b.EFFECTIVE_FROM) is True
    assert period.temporal_refusal_at(b.EFFECTIVE_FROM) is None


def test_one_microsecond_before_the_start_is_not_yet_effective():
    period = _bounded()
    instant = b.EFFECTIVE_FROM - MICRO
    assert period.is_effective_at(instant) is False
    assert period.temporal_refusal_at(instant) is _R.BENCHMARK_NOT_YET_EFFECTIVE


def test_the_end_bound_is_exclusive():
    period = _bounded()
    assert period.is_effective_at(b.EFFECTIVE_TO) is False
    assert period.temporal_refusal_at(b.EFFECTIVE_TO) is _R.BENCHMARK_EXPIRED


def test_one_microsecond_before_the_end_is_still_effective():
    period = _bounded()
    instant = b.EFFECTIVE_TO - MICRO
    assert period.is_effective_at(instant) is True
    assert period.temporal_refusal_at(instant) is None


def test_well_after_the_end_is_expired():
    period = _bounded()
    instant = b.EFFECTIVE_TO + timedelta(days=365)
    assert period.is_effective_at(instant) is False
    assert period.temporal_refusal_at(instant) is _R.BENCHMARK_EXPIRED


# --------------------------------------------------------------------------- #
# Open-ended periods
# --------------------------------------------------------------------------- #
def test_an_open_ended_period_never_expires():
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    far = datetime(2999, 1, 1, tzinfo=timezone.utc)
    assert period.is_effective_at(far) is True
    assert period.temporal_refusal_at(far) is None


def test_an_open_ended_period_still_has_a_start_bound():
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    assert period.is_effective_at(b.BEFORE) is False
    assert period.temporal_refusal_at(b.BEFORE) is _R.BENCHMARK_NOT_YET_EFFECTIVE


# --------------------------------------------------------------------------- #
# The instant is a parameter, never an ambient read
# --------------------------------------------------------------------------- #
def test_the_instant_is_mandatory():
    period = _bounded()
    with pytest.raises(TypeError):
        period.is_effective_at()
    with pytest.raises(TypeError):
        period.temporal_refusal_at()


def test_a_naive_instant_is_refused_rather_than_assumed_utc():
    period = _bounded()
    naive = datetime(2026, 6, 1, 0, 0, 0)
    with pytest.raises(BenchmarkContractError):
        period.is_effective_at(naive)
    with pytest.raises(BenchmarkContractError):
        period.temporal_refusal_at(naive)


def test_a_datetime_subclass_is_refused():
    class Sneaky(datetime):
        pass

    period = _bounded()
    with pytest.raises(BenchmarkContractError):
        period.is_effective_at(Sneaky(2026, 6, 1, tzinfo=timezone.utc))


def test_offsets_are_compared_as_instants_not_as_wall_clocks():
    period = _bounded()
    tz = timezone(timedelta(hours=-5))
    same_instant = b.EFFECTIVE_TO.astimezone(tz)
    assert same_instant == b.EFFECTIVE_TO
    assert period.is_effective_at(same_instant) is False
    assert period.temporal_refusal_at(same_instant) is _R.BENCHMARK_EXPIRED


# --------------------------------------------------------------------------- #
# The identity delegates, and reports the same boundaries
# --------------------------------------------------------------------------- #
def test_the_identity_delegates_to_its_declared_period():
    identity = b.identity()
    assert identity.is_effective_at(b.INSIDE) is True
    assert identity.is_effective_at(b.EFFECTIVE_TO) is False
    assert identity.temporal_refusal_at(b.EFFECTIVE_TO) is _R.BENCHMARK_EXPIRED
    assert identity.temporal_refusal_at(b.BEFORE) is _R.BENCHMARK_NOT_YET_EFFECTIVE


def test_being_within_the_period_is_not_a_pass():
    """No temporal refusal still leaves everything else unestablished (B-9)."""

    identity = b.identity()
    assert identity.temporal_refusal_at(b.INSIDE) is None
    assert identity.trusted_resolution_performed is False
    assert (
        _R.BENCHMARK_RESOLUTION_NOT_PERFORMED
        in identity.structural_refusals_at(b.INSIDE)
    )


def test_a_temporal_refusal_and_a_lifecycle_refusal_are_reported_together():
    from ugence_benchmark_registry.api import BenchmarkLifecycleState

    identity = b.identity(lifecycle_state=BenchmarkLifecycleState.REVOKED)
    refusals = identity.structural_refusals_at(b.BEFORE)
    assert _R.BENCHMARK_NOT_YET_EFFECTIVE in refusals
    assert _R.BENCHMARK_REVOKED in refusals
    assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in refusals


def test_the_refusal_sequence_is_deterministic():
    identity = b.identity()
    first = identity.structural_refusals_at(b.EFFECTIVE_TO)
    for _ in range(5):
        assert identity.structural_refusals_at(b.EFFECTIVE_TO) == first
