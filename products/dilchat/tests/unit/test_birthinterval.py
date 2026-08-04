"""Birth-time interval computation across EXACT / APPROXIMATE / UNKNOWN (Area B)."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_dilchat.domain.enums import BirthTimePrecision
from ugence_dilchat.errors import DilChatError, ErrorCode
from ugence_dilchat.services.birthtime import compute_birth_interval


def _iv(**kw):
    base = dict(
        birth_date=dt.date(1990, 5, 15),
        birth_time_local=dt.time(14, 30),
        iana_timezone="Asia/Kolkata",
        ambiguity_resolution=None,
        uncertainty_minutes=None,
    )
    base.update(kw)
    return compute_birth_interval(**base)


def test_exact_is_point_interval():
    r = _iv(precision=BirthTimePrecision.EXACT)
    assert r.is_exact is True
    assert r.utc_start == r.utc_end == dt.datetime(1990, 5, 15, 9, 0, tzinfo=dt.UTC)


def test_approximate_requires_uncertainty():
    with pytest.raises(DilChatError) as exc:
        _iv(precision=BirthTimePrecision.APPROXIMATE, uncertainty_minutes=None)
    assert exc.value.code is ErrorCode.MISSING_APPROXIMATION_INTERVAL


def test_approximate_symmetric_interval():
    r = _iv(precision=BirthTimePrecision.APPROXIMATE, uncertainty_minutes=15)
    assert not r.is_exact
    assert r.uncertainty_minutes == 15
    assert (r.utc_end - r.utc_start) == dt.timedelta(minutes=30)
    center = dt.datetime(1990, 5, 15, 9, 0, tzinfo=dt.UTC)
    assert r.utc_start == center - dt.timedelta(minutes=15)
    assert r.utc_end == center + dt.timedelta(minutes=15)


def test_approximate_rejects_excessive_interval():
    with pytest.raises(DilChatError) as exc:
        _iv(precision=BirthTimePrecision.APPROXIMATE, uncertainty_minutes=1000)
    assert exc.value.code is ErrorCode.VALIDATION_ERROR


def test_approximate_rejects_nonpositive():
    with pytest.raises(DilChatError):
        _iv(precision=BirthTimePrecision.APPROXIMATE, uncertainty_minutes=0)


def test_unknown_is_full_civil_day():
    r = _iv(precision=BirthTimePrecision.UNKNOWN, birth_time_local=None)
    assert not r.is_exact
    assert r.time_assumption == "UNKNOWN_CIVIL_DAY_INTERVAL"
    # IST has no DST: exactly 24h.
    assert (r.utc_end - r.utc_start) == dt.timedelta(hours=24)
    # Day starts 00:00 IST = 18:30 UTC previous day.
    assert r.utc_start == dt.datetime(1990, 5, 14, 18, 30, tzinfo=dt.UTC)


def test_unknown_long_civil_day_on_dst_fallback():
    # US fall-back day 2021-11-07 has 25 local hours in America/New_York.
    r = compute_birth_interval(
        birth_date=dt.date(2021, 11, 7),
        birth_time_local=None,
        precision=BirthTimePrecision.UNKNOWN,
        iana_timezone="America/New_York",
        ambiguity_resolution=None,
        uncertainty_minutes=None,
    )
    assert (r.utc_end - r.utc_start) == dt.timedelta(hours=25)


def test_unknown_short_civil_day_on_dst_springforward():
    # US spring-forward day 2021-03-14 has 23 local hours.
    r = compute_birth_interval(
        birth_date=dt.date(2021, 3, 14),
        birth_time_local=None,
        precision=BirthTimePrecision.UNKNOWN,
        iana_timezone="America/New_York",
        ambiguity_resolution=None,
        uncertainty_minutes=None,
    )
    assert (r.utc_end - r.utc_start) == dt.timedelta(hours=23)
