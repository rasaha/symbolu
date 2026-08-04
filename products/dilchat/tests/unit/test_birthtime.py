"""Unit tests for local->UTC birth-time conversion and DST edge cases."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_dilchat.domain.enums import AmbiguityResolution, BirthTimePrecision
from ugence_dilchat.errors import DilChatError, ErrorCode
from ugence_dilchat.services.birthtime import compute_birth_instant


def test_simple_conversion_ist():
    # IST is UTC+5:30 with no DST.
    r = compute_birth_instant(
        birth_date=dt.date(1990, 5, 15),
        birth_time_local=dt.time(14, 30),
        precision=BirthTimePrecision.EXACT,
        iana_timezone="Asia/Kolkata",
        ambiguity_resolution=None,
    )
    assert r.utc_instant == dt.datetime(1990, 5, 15, 9, 0, tzinfo=dt.UTC)
    assert not r.is_ambiguous and not r.is_nonexistent


def test_historical_offset_pre_1970():
    # Uses the historical tz database, not a fixed modern offset.
    r = compute_birth_instant(
        birth_date=dt.date(1945, 1, 1),
        birth_time_local=dt.time(6, 0),
        precision=BirthTimePrecision.EXACT,
        iana_timezone="Asia/Kolkata",
        ambiguity_resolution=None,
    )
    assert r.utc_instant is not None
    assert r.utc_instant.tzinfo == dt.UTC


def test_unknown_time_no_instant():
    r = compute_birth_instant(
        birth_date=dt.date(1990, 5, 15),
        birth_time_local=None,
        precision=BirthTimePrecision.UNKNOWN,
        iana_timezone="Asia/Kolkata",
        ambiguity_resolution=None,
    )
    assert r.utc_instant is None
    assert r.time_assumption == "UNKNOWN_TIME_NO_INSTANT"


def test_nonexistent_local_time_rejected():
    # US spring-forward 2021-03-14 02:30 does not exist in America/New_York.
    with pytest.raises(DilChatError) as exc:
        compute_birth_instant(
            birth_date=dt.date(2021, 3, 14),
            birth_time_local=dt.time(2, 30),
            precision=BirthTimePrecision.EXACT,
            iana_timezone="America/New_York",
            ambiguity_resolution=None,
        )
    assert exc.value.code is ErrorCode.NONEXISTENT_LOCAL_TIME


def test_ambiguous_local_time_requires_resolution():
    # US fall-back 2021-11-07 01:30 occurs twice in America/New_York.
    with pytest.raises(DilChatError) as exc:
        compute_birth_instant(
            birth_date=dt.date(2021, 11, 7),
            birth_time_local=dt.time(1, 30),
            precision=BirthTimePrecision.EXACT,
            iana_timezone="America/New_York",
            ambiguity_resolution=None,
        )
    assert exc.value.code is ErrorCode.AMBIGUOUS_LOCAL_TIME


def test_ambiguous_resolution_earlier_vs_later_differ():
    earlier = compute_birth_instant(
        birth_date=dt.date(2021, 11, 7),
        birth_time_local=dt.time(1, 30),
        precision=BirthTimePrecision.EXACT,
        iana_timezone="America/New_York",
        ambiguity_resolution=AmbiguityResolution.EARLIER,
    )
    later = compute_birth_instant(
        birth_date=dt.date(2021, 11, 7),
        birth_time_local=dt.time(1, 30),
        precision=BirthTimePrecision.EXACT,
        iana_timezone="America/New_York",
        ambiguity_resolution=AmbiguityResolution.LATER,
    )
    assert earlier.is_ambiguous and later.is_ambiguous
    assert earlier.utc_instant != later.utc_instant
    # EEST->EST: EARLIER (EDT, -4) is one hour before LATER (EST, -5).
    assert later.utc_instant - earlier.utc_instant == dt.timedelta(hours=1)


def test_unknown_timezone_rejected():
    with pytest.raises(DilChatError) as exc:
        compute_birth_instant(
            birth_date=dt.date(1990, 5, 15),
            birth_time_local=dt.time(14, 30),
            precision=BirthTimePrecision.EXACT,
            iana_timezone="Mars/Phobos",
            ambiguity_resolution=None,
        )
    assert exc.value.code is ErrorCode.VALIDATION_ERROR
